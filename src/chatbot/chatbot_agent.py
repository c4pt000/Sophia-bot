# -*- coding: utf-8 -*-
import logging
import random
import os
import re
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import atexit
from collections import defaultdict

from threading import RLock
sync = RLock()

SUCCESS = 0
WRONG_CHARACTER_NAME = 1
NO_PATTERN_MATCH = 2
INVALID_SESSION = 3
INVALID_QUESTION = 4

logger = logging.getLogger('hr.chatbot.server.chatbot_agent')

from loader import load_characters
from config import CHARACTER_PATH, RESET_SESSION_BY_HELLO, config
CHARACTERS = load_characters(CHARACTER_PATH)
REVISION = os.environ.get('HR_CHATBOT_REVISION')

from session import ChatSessionManager
session_manager = ChatSessionManager()
DISABLE_QUIBBLE = True

from chatbot.utils import shorten, str_cleanup, get_weather, parse_weather
from chatbot.words2num import words2num
from chatbot.server.character import TYPE_AIML, TYPE_CS
from operator import add, sub, mul, truediv, pow
import math
from chatbot.server.template import render

OPERATOR_MAP = {
    '[add]': add,
    '[sub]': sub,
    '[mul]': mul,
    '[div]': truediv,
    '[pow]': pow,
}

def get_character(id, lang=None, ns=None):
    for character in CHARACTERS:
        if (ns is not None and character.name != ns) or character.id != id:
            continue
        if lang is None:
            return character
        elif lang in character.languages:
            return character


def add_character(character):
    if character.id not in [c.id for c in CHARACTERS]:
        CHARACTERS.append(character)
        return True, "Character added"
    # TODO: Update character
    else:
        return False, "Character exists"


def is_local_character(character):
    return character.local


def get_characters_by_name(name, local=True, lang=None, user=None):
    characters = []
    _characters = [c for c in CHARACTERS if c.name == name]
    if local:
        _characters = [c for c in _characters if is_local_character(c)]
    if lang is not None:
        _characters = [c for c in _characters if lang in c.languages]

    if user is not None:
        for c in _characters:
            toks = c.id.split('/')
            if len(toks) == 2:
                if toks[0] == user:
                    characters.append(c)
            else:
                characters.append(c)
    else:
        characters = _characters
    if not characters:
        logger.warn('No character is satisfied')
    return characters


def list_character(lang, sid):
    sess = session_manager.get_session(sid)
    if sess is None:
        return []
    characters = get_responding_characters(lang, sid)
    weights = get_weights(characters, sess)
    return [(c.name, c.id, w, c.level, c.dynamic_level) for c, w in zip(characters, weights)]


def list_character_names():
    names = list(set([c.name for c in CHARACTERS if c.name != 'dummy']))
    return names


def set_weights(param, lang, sid):
    sess = session_manager.get_session(sid)
    if sess is None:
        return False, "No session"

    if param == 'reset':
        sess.sdata.weights = {}
        return True, "Weights are reset"

    weights = {}
    characters = get_responding_characters(lang, sid)
    try:
        for w in param.split(','):
            k, v = w.split('=')
            v = float(v)
            if v>1 or v<0:
                return False, "Weight must be in the range [0, 1]"
            try:
                k = int(k)
                weights[characters[k].id] = v
            except ValueError:
                weights[k] = v
    except Exception as ex:
        logger.error(ex)
        return False, "Wrong weight format"

    sess.sdata.weights = weights
    return True, "Weights are updated"

def get_weights(characters, sess):
    weights = []
    if hasattr(sess.sdata, 'weights') and sess.sdata.weights:
        for c in characters:
            if c.id in sess.sdata.weights:
                weights.append(sess.sdata.weights.get(c.id))
            else:
                weights.append(c.weight)
    else:
        weights = [c.weight for c in characters]
    return weights

def set_context(prop, sid):
    sess = session_manager.get_session(sid)
    if sess is None:
        return False, "No session"
    for c in CHARACTERS:
        try:
            c.set_context(sess, prop)
        except Exception:
            pass
    return True, "Context is updated"

def remove_context(keys, sid):
    sess = session_manager.get_session(sid)
    if sess is None:
        return False, "No session"
    for c in CHARACTERS:
        if c.type != TYPE_AIML and c.type != TYPE_CS:
            continue
        try:
            for key in keys:
                c.remove_context(sess, key)
        except Exception:
            pass
    return True, "Context is updated"

def get_context(sid):
    sess = session_manager.get_session(sid)
    if sess is None:
        return False, "No session"
    context = {}
    for c in CHARACTERS:
        if c.type != TYPE_AIML and c.type != TYPE_CS:
            continue
        try:
            context.update(c.get_context(sess))
        except Exception:
            pass
    for k in context.keys():
        if k.startswith('_'):
            del context[k]
    return True, context

def update_config(**kwargs):
    keys = []
    for key, value in kwargs.items():
        if key in config:
            if isinstance(value, unicode):
                value = str(value)
            config[key] = value
            if key not in keys:
                keys.append(key)
        else:
            logger.warn("Unknown config {}".format(key))

    if len(keys) > 0:
        logger.warn("Configuration is updated")
        for key in keys:
            logger.warn("{}={}".format(key, config[key]))
        return True, "Configuration is updated"
    else:
        return False, "No configuration is updated"

def preprocessing(question, lang, session):
    question = question.lower().strip()
    question = ' '.join(question.split())  # remove consecutive spaces
    question = question.replace('sofia', 'sophia')

    reduction = get_character('reduction')
    if reduction is not None:
        response = reduction.respond(question, lang, session, query=True, request_id=request_id)
        reducted_text = response.get('text')
        if reducted_text:
            question = reducted_text

    return question

def _ask_characters(characters, question, lang, sid, query, request_id, **kwargs):
    sess = session_manager.get_session(sid)
    if sess is None:
        return

    used_charaters = []
    data = sess.get_session_data()
    user = getattr(data, 'user')
    botname = getattr(data, 'botname')
    weights = get_weights(characters, sess)
    weighted_characters = zip(characters, weights)
    logger.info("Weights {}".format(weighted_characters))

    _question = preprocessing(question, lang, sess)
    response = {}
    hit_character = None
    answer = None
    cross_trace = []
    cached_responses = defaultdict(list)

    control = get_character('control')
    if control is not None:
        _response = control.respond(_question, lang, sess, query, request_id)
        _answer = _response.get('text')
        if _answer == '[tell me more]':
            cross_trace.append((control.id, 'control', _response.get('trace') or 'No trace'))
            if sess.last_used_character:
                if sess.cache.that_question is None:
                    sess.cache.that_question = sess.cache.last_question
                context = sess.last_used_character.get_context(sess)
                if 'continue' in context and context.get('continue'):
                    _answer, res = shorten(context.get('continue'), 140)
                    response['text'] = answer = _answer
                    response['botid'] = sess.last_used_character.id
                    response['botname'] = sess.last_used_character.name
                    sess.last_used_character.set_context(sess, {'continue': res})
                    hit_character = sess.last_used_character
                    cross_trace.append((sess.last_used_character.id, 'continuation', 'Non-empty'))
                else:
                    _question = sess.cache.that_question.lower().strip()
                    cross_trace.append((sess.last_used_character.id, 'continuation', 'Empty'))
        elif _answer.startswith('[weather]'):
            template = _answer.replace('[weather]', '')
            cross_trace.append((control.id, 'control', _response.get('trace') or 'No trace'))
            context = control.get_context(sess)
            if context:
                location = context.get('querylocation')
                prop = parse_weather(get_weather(location))
                if prop:
                    try:
                        _answer = template.format(location=location, **prop)
                        if _answer:
                            answer = _answer
                            response['text'] = _answer
                            response['botid'] = control.id
                            response['botname'] = control.name
                    except Exception as ex:
                        cross_trace.append((control.id, 'control', 'No answer'))
                        logger.error(ex)
                else:
                    cross_trace.append((control.id, 'control', 'No answer'))
        elif _answer in OPERATOR_MAP.keys():
            opt = OPERATOR_MAP[_answer]
            cross_trace.append((control.id, 'control', _response.get('trace') or 'No trace'))
            context = control.get_context(sess)
            if context:
                item1 = context.get('item1')
                item2 = context.get('item2')
                item1 = words2num(item1)
                item2 = words2num(item2)
                if item1 is not None and item2 is not None:
                    try:
                        result = opt(item1, item2)
                        img = math.modf(result)[0]
                        if img < 1e-6:
                            result_str = '{:d}'.format(int(result))
                        else:
                            result_str = 'about {:.4f}'.format(result)
                        if result > 1e20:
                            answer = "The number is too big. You should use a calculator."
                        else:
                            answer = "The answer is {result}".format(result=result_str)
                    except ZeroDivisionError:
                        answer = "Oh, the answer is not a number"
                    except Exception as ex:
                        logger.error(ex)
                        answer = "Sorry, something goes wrong. I can't calculate it."
                    response['text'] = answer
                    response['botid'] = control.id
                    response['botname'] = control.name
                else:
                    cross_trace.append((control.id, 'control', 'No answer'))
        else:
            if _answer and not re.findall(r'\[.*\].*', _answer):
                cross_trace.append((control.id, 'control', _response.get('trace') or 'No trace'))
                hit_character = control
                answer = _answer
                response = _response
            else:
                cross_trace.append((control.id, 'control', 'No answer'))
            for c in characters:
                try:
                    c.remove_context(sess, 'continue')
                except NotImplementedError:
                    pass
            sess.cache.that_question = None

    def _ask_character(stage, character, weight, good_match=False, reuse=False):
        logger.info("Asking character {} in stage {}".format(character.id, stage))

        if not reuse and character.id in used_charaters:
            cross_trace.append((character.id, stage, 'Skip used tier'))
            return False, None, None

        if character.id in used_charaters and character.type == TYPE_CS:
            cross_trace.append((character.id, stage, 'Skip CS tier'))
            return False, None, None

        used_charaters.append(character.id)
        answer = None
        answered = False

        if weight == 0:
            cross_trace.append((character.id, stage, 'Disabled'))
            return False, None, None

        response = character.respond(_question, lang, sess, query, request_id)
        answer = str_cleanup(response.get('text', ''))
        trace = response.get('trace')

        if answer:
            if 'pickup' in character.id:
                cached_responses['pickup'].append((response, answer, character))
                return False, None, None
            if good_match:
                if response.get('exact_match') or response.get('ok_match'):
                    logger.info("{} has good match".format(character.id))
                    answered = True
                else:
                    logger.info("{} has no good match".format(character.id))
                    cross_trace.append((character.id, stage, 'No good match. Answer: {}, Trace: {}'.format(answer, trace)))
                    cached_responses['nogoodmatch'].append((response, answer, character))
            elif response.get('bad'):
                cross_trace.append((character.id, stage, 'Bad answer. Answer: {}, Trace: {}'.format(answer, trace)))
                cached_responses['bad'].append((response, answer, character))
            elif DISABLE_QUIBBLE and response.get('quibble'):
                cross_trace.append((character.id, stage, 'Quibble answer. Answer: {}, Trace: {}'.format(answer, trace)))
                cached_responses['quibble'].append((response, answer, character))
            elif response.get('gambit'):
                if random.random() > 0.3:
                    cross_trace.append((character.id, stage, 'Ignore gambit answer. Answer: {}, Trace: {}'.format(answer, trace)))
                    cached_responses['gambit'].append((response, answer, character))
                else:
                    answered = True
            else:
                answered = True
            if answered:
                if random.random() < weight:
                    cross_trace.append((character.id, stage, 'Trace: {}'.format(trace)))
                else:
                    answered = False
                    cross_trace.append((character.id, stage, 'Pass through. Answer: {}, Weight: {}, Trace: {}'.format(answer, weight, trace)))
                    logger.info("{} has no answer".format(character.id))
                    if 'markov' not in character.id:
                        cached_responses['pass'].append((response, answer, character))
                    else:
                        cached_responses['?'].append((response, answer, character))
        else:
            if response.get('repeat'):
                answer = response.get('repeat')
                cross_trace.append((character.id, stage, 'Repetitive answer. Answer: {}, Trace: {}'.format(answer, trace)))
                cached_responses['repeat'].append((response, answer, character))
            else:
                logger.info("{} has no answer".format(character.id))
                cross_trace.append((character.id, stage, 'No answer. Trace: {}'.format(trace)))
        return answered, answer, response

    # If the last input is a question, then try to use the same tier to
    # answer it.
    if not answer:
        if sess.open_character in characters:
            answered, _answer, _response = _ask_character(
                'question', sess.open_character, 1, good_match=True)
            if answered:
                hit_character = sess.open_character
                answer = _answer
                response = _response

    # Try the first tier to see if there is good match
    if not answer:
        c, weight = weighted_characters[0]
        answered, _answer, _response = _ask_character(
            'priority', c, weight, good_match=True)
        if answered:
            hit_character = c
            answer = _answer
            response = _response

    # Select tier that is designed to be proper to answer the question
    if not answer:
        for c, weight in weighted_characters:
            if c.is_favorite(_question):
                answered, _answer, _response = _ask_character(
                    'favorite', c, 1)
                if answered:
                    hit_character = c
                    answer = _answer
                    response = _response

    # Check the last used character
    if not answer:
        if sess.last_used_character and sess.last_used_character.dynamic_level:
            for c, weight in weighted_characters:
                if sess.last_used_character.id == c.id:
                    answered, _answer, _response = _ask_character(
                        'last used', c, weight)
                    if answered:
                        hit_character = c
                        answer = _answer
                        response = _response
                    break

    # Check the loop
    if not answer:
        for c, weight in weighted_characters:
            answered, _answer, _response = _ask_character(
                'loop', c, weight, reuse=True)
            if answered:
                hit_character = c
                answer = _answer
                response = _response
                break

    if not answer:
        for response_type in ['pass', 'nogoodmatch', 'quibble', 'repeat', 'gambit', 'pickup', 'bad', '?']:
            if cached_responses.get(response_type):
                response, answer, hit_character = cached_responses.get(response_type)[0]
                if response_type == 'repeat':
                    if len(answer) < 80:
                        answer = "Again. " + answer
                    elif 80 < len(answer) < 200:
                        answer = "Let me say again. " + answer
                    else:
                        continue
                response['text'] = answer
                cross_trace.append(
                    (hit_character.id, response_type,
                    response.get('trace') or 'No trace'))
                break

    if answer and re.match('.*{.*}.*', answer):
        logger.info("Template answer {}".format(answer))
        try:
            response['orig_text'] = answer
            answer = render(answer)
            response['text'] = answer
        except Exception as ex:
            answer = ''
            response['text'] = ''
            logger.error("Error in rendering template, {}".format(ex))

    dummy_character = get_character('dummy', lang)
    if not answer and dummy_character:
        if response.get('repeat'):
            response = dummy_character.respond("REPEAT_ANSWER", lang, sid, query)
        else:
            response = dummy_character.respond("NO_ANSWER", lang, sid, query)
        hit_character = dummy_character
        answer = str_cleanup(response.get('text', ''))

    if not query and hit_character is not None:
        sess.add(question, answer, AnsweredBy=hit_character.id,
                    User=user, BotName=botname, Trace=cross_trace,
                    Revision=REVISION, Lang=lang, ModQuestion=_question,
                    RequestId=request_id,Marker=kwargs.get('marker'))

        sess.last_used_character = hit_character

        if is_question(answer.lower().strip()):
            if hit_character.dynamic_level:
                sess.open_character = hit_character
                logger.info("Set open dialog character {}".format(
                            hit_character.id))
        else:
            sess.open_character = None

    response['trace'] = cross_trace
    return response

def is_question(question):
    if not isinstance(question, unicode):
        question = question.decode('utf-8')
    return question.endswith('?') or question.endswith('？')

def get_responding_characters(lang, sid):
    sess = session_manager.get_session(sid)
    if sess is None:
        return []
    if not hasattr(sess.sdata, 'botname'):
        return []

    botname = sess.sdata.botname
    user = sess.sdata.user

    # current character > local character with the same name > solr > generic
    responding_characters = get_characters_by_name(
        botname, local=False, lang=lang, user=user)
    responding_characters = sorted(responding_characters, key=lambda x: x.level)

    generic = get_character('generic', lang)
    if generic:
        if generic not in responding_characters:
            # get shared properties
            character = get_character(botname)
            generic.set_properties(character.get_properties())
            responding_characters.append(generic)
    else:
        logger.info("Generic character is not found")

    responding_characters = sorted(responding_characters, key=lambda x: x.level)

    return responding_characters


def rate_answer(sid, idx, rate):
    sess = session_manager.get_session(sid)
    if sess is None:
        logger.error("Session doesn't exist")
        return False
    try:
        return sess.rate(rate, idx)
    except Exception as ex:
        logger.error("Rate error: {}".format(ex))
        return False
    return True


def ask(question, lang, sid, query=False, request_id=None, **kwargs):
    """
    return (response dict, return code)
    """
    response = {'text': '', 'emotion': '', 'botid': '', 'botname': ''}

    sess = session_manager.get_session(sid)
    if sess is None:
        return response, INVALID_SESSION

    if not question or not question.strip():
        return response, INVALID_QUESTION

    responding_characters = get_responding_characters(lang, sid)
    if not responding_characters:
        logger.error("Wrong characer name")
        return response, WRONG_CHARACTER_NAME

    # Handle commands
    if question == ':reset':
        session_manager.dump(sid)
        session_manager.reset_session(sid)
        logger.warn("Session {} is reset by :reset".format(sid))
    for c in responding_characters:
        if c.is_command(question):
            response.update(c.respond(question, lang, sess, query, request_id))
            return response, SUCCESS

    response['yousaid'] = question

    sess.set_characters(responding_characters)
    if RESET_SESSION_BY_HELLO and question:
        question_tokens = question.lower().strip().split()
        if 'hi' in question_tokens or 'hello' in question_tokens:
            session_manager.dump(sid)
            session_manager.reset_session(sid)
            logger.warn("Session {} is reset by greeting".format(sid))
    if question and question.lower().strip() in ["what's new"]:
        sess.last_used_character = None
        sess.open_character = None
        logger.info("Triggered new topic")

    logger.info("Responding characters {}".format(responding_characters))
    _response = _ask_characters(
        responding_characters, question, lang, sid, query, request_id, **kwargs)

    if not query:
        # Sync session data
        if sess.last_used_character is not None:
            context = sess.last_used_character.get_context(sess)
            for c in responding_characters:
                if c.id == sess.last_used_character.id:
                    continue
                try:
                    c.set_context(sess, context)
                except NotImplementedError:
                    pass

            for c in responding_characters:
                if c.type != TYPE_AIML:
                    continue
                try:
                    c.check_reset_topic(sid)
                except Exception:
                    continue

    if _response is not None and _response.get('text'):
        response.update(_response)
        logger.info("Ask {}, response {}".format(question, response))
        return response, SUCCESS
    else:
        logger.error("No pattern match")
        return response, NO_PATTERN_MATCH

def said(sid, text):
    sess = session_manager.get_session(sid)
    if sess is None:
        return False, "No session"
    control = get_character('control')
    if control is not None:
        control.said(sess, text)
        return True, "Done"
    return False, 'No control tier'

def dump_history():
    return session_manager.dump_all()


def dump_session(sid):
    return session_manager.dump(sid)


def reload_characters(**kwargs):
    global CHARACTERS, REVISION
    with sync:
        characters = None
        logger.info("Reloading")
        try:
            characters = load_characters(CHARACTER_PATH)
            del CHARACTERS[:]
            CHARACTERS = characters
            revision = kwargs.get('revision')
            if revision:
                REVISION = revision
                logger.info("Revision {}".format(revision))
        except Exception as ex:
            logger.error("Reloading characters error {}".format(ex))

def rebuild_cs_character(**kwargs):
    with sync:
        try:
            botname=kwargs.get('botname')
            characters=get_characters_by_name(botname)
            if not characters:
                logger.error("Can't find CS tier for {}".format(botname))
            for c in characters:
                if c.id == 'cs' and hasattr(c, 'rebuild'):
                    log = c.rebuild()
                    if 'ERROR SUMMARY' in log:
                        logger.error(log[log.index('ERROR SUMMARY'):])
                    logger.info("Rebuilding chatscript for {} successfully".format(botname))
        except Exception as ex:
            logger.error("Rebuilding chatscript characters error {}".format(ex))

atexit.register(dump_history)
