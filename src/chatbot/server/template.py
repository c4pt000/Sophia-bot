import os
from jinja2 import Template, Environment, meta
from renderers import *
import logging

logger = logging.getLogger('hr.chatbot.server.template')

def render(string):
    t = Template(string)
    func = get_render_func(string)
    if func is not None:
        try:
            return func(t) or t.render()
        except Exception as ex:
            logger.error("Rendering error, {}".format(ex))
            return t.render()
    else:
        logger.error("Render is not found for template {}".format(string))
        return t.render()

def get_render_func(string):
    func = None
    env = Environment()
    ast = env.parse(string)
    variables = meta.find_undeclared_variables(ast)
    if 'temperature' in variables:
        func = render_weather
    if 'location' in variables:
        func = render_location
    if 'faceemotion' in variables:
        func = render_face_emotion
    if 'objectdetected' in variables:
        func = render_object_detected
    return func

if __name__ == '__main__':
    string = """{% set location = "hong kong" %} {% if temperature is not defined %} I don't know {% elif temperature>30 %} it's really hot {% elif temperature<10 %} too cold here {% else %} Hmm, it\'s nice {% endif %}."""
    string  = render(string)
    print string

    string = """{% if temperature is not defined %} I don't know {% else %} The weather is {{ weather_desc }}, the temperature is {{ temperature }}. {% endif %}"""
    string  = render(string)
    print string

    string = """I think you are in {{ location }}. """
    string  = render(string)
    print string

    string = """{% if faceemotion is not defined %} I can't tell. How do you feel? {% else %} You look {{ faceemotion }}. {% endif %}"""
    string  = render(string)
    print string

    string = """{% if objectdetected is not defined %} Sorry, I don't know what's that. {% else %} Is that {{ objectdetected }}. {% endif %}"""
    string  = render(string)
    print string
