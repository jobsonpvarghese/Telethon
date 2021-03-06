import asyncio
import difflib
import logging
import os
import sys
import time
import urllib.parse

from telethon import TelegramClient, events, custom

logging.basicConfig(level=logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.ERROR)

for x in 'TG_API_ID TG_API_HASH TG_TOKEN'.split():
    if x not in os.environ:
        print(f'{x} not in environmental variables', file=sys.stderr)
        quit()

NAME = os.environ['TG_TOKEN'].split(':')[0]
bot = TelegramClient(NAME, os.environ['TG_API_ID'], os.environ['TG_API_HASH'])


# ============================== Constants ==============================
WELCOME = (
    'Hi and welcome to the group. Before asking any questions, **please** '
    'read [the docs](https://telethon.readthedocs.io/). Make sure you are '
    'using the latest version with `pip3 install -U telethon`, since most '
    'problems have already been fixed in newer versions.'
)

READ_FULL = (
    'Please read [Accessing the Full API](https://telethon.readthedocs.io'
    '/en/latest/extra/advanced-usage/accessing-the-full-api.html)'
)

SEARCH = (
    'Remember [search is your friend]'
    '(https://lonamiwebs.github.io/Telethon/?q={})'
)

DOCS = 'TL Reference for [{}](https://lonamiwebs.github.io/Telethon/?q={})'
RTD = '[Read The Docs!](https://telethon.readthedocs.io)'
RTFD = '[Read The F* Docs!](https://telethon.readthedocs.io)'
DOCS_CLIENT = 'https://telethon.readthedocs.io/en/latest/telethon.client.html#'
DOCS_MESSAGE = (
    'https://telethon.readthedocs.io/en/latest/'
    'telethon.tl.custom.html#telethon.tl.custom.message.Message.'
)
# ============================== Constants ==============================
# ==============================  Welcome  ==============================
last_welcome = None


@bot.on(events.ChatAction)
async def handler(event):
    if event.user_joined:
        global last_welcome
        if last_welcome is not None:
            await last_welcome.delete()

        last_welcome = await event.reply(WELCOME)


# ==============================  Welcome  ==============================
# ==============================  Commands ==============================


@bot.on(events.NewMessage(pattern='#ping', forwards=False))
async def handler(event):
    s = time.time()
    message = await event.reply('Pong!')
    d = time.time() - s
    await message.edit(f'Pong! __(reply took {d:.2f}s)__')
    await asyncio.sleep(5)
    await asyncio.wait([event.delete(), message.delete()])


@bot.on(events.NewMessage(pattern='#full', forwards=False))
async def handler(event):
    """#full: Advises to read "Accessing the full API" in the docs."""
    await asyncio.wait([
        event.delete(),
        event.respond(READ_FULL, reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='#search (.+)', forwards=False))
async def handler(event):
    """#search query: Searches for "query" in the method reference."""
    query = urllib.parse.quote(event.pattern_match.group(1))
    await asyncio.wait([
        event.delete(),
        event.respond(SEARCH.format(query), reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='(?i)#(?:docs|ref) (.+)', forwards=False))
async def handler(event):
    """#docs or #ref query: Like #search but shows the query."""
    q1 = event.pattern_match.group(1)
    q2 = urllib.parse.quote(q1)
    await asyncio.wait([
        event.delete(),
        event.respond(DOCS.format(q1, q2), reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='#rt(f)?d', forwards=False))
async def handler(event):
    """#rtd: Tells the user to please read the docs."""
    rtd = RTFD if event.pattern_match.group(1) else RTD
    await asyncio.wait([
        event.delete(),
        event.respond(rtd, reply_to=event.reply_to_msg_id)
    ])


@bot.on(events.NewMessage(pattern='(?i)#(client|msg) (.+)', forwards=False))
async def handler(event):
    """#client or #msg query: Looks for the given attribute in RTD."""
    await event.delete()
    query = event.pattern_match.group(2).lower()
    cls = ({'client': TelegramClient, 'msg': custom.Message}
           [event.pattern_match.group(1)])

    attr = search_attr(cls, query)
    if not attr:
        await event.respond(f'No such method "{query}" :/')
        return

    name = attr
    if event.pattern_match.group(1) == 'client':
        attr = attr_fullname(cls, attr)
        url = DOCS_CLIENT
    elif event.pattern_match.group(1) == 'msg':
        name = f'Message.{name}'
        url = DOCS_MESSAGE
    else:
        return

    await event.respond(
        f'Documentation for [{name}]({url}{attr})',
        reply_to=event.reply_to_msg_id
    )


@bot.on(events.NewMessage(pattern='#list', forwards=False))
async def handler(event):
    await event.delete()
    text = 'Available commands:\n'
    for callback, handler in bot.list_event_handlers():
        if isinstance(handler, events.NewMessage) and callback.__doc__:
            text += f'\n{callback.__doc__}'

    message = await event.respond(text)
    await asyncio.sleep(1 * text.count(' '))  # Sleep ~1 second per word
    await message.delete()


# ==============================  Commands ==============================
# ============================== AutoReply ==============================


@bot.on(events.NewMessage(pattern='(?i)how (.+?)[\W]*$', forwards=False))
@bot.on(events.NewMessage(pattern='(.+?)[\W]*?\?+', forwards=False))
async def handler(event):
    words = event.pattern_match.group(1).split()
    rates = [
        search_attr(TelegramClient, ' '.join(words[-i:]), threshold=None)
        for i in range(1, 4)
    ]
    what = max(rates, key=lambda t: t[1])
    if what[1] < 0.7:
        return

    name = what[0]
    attr = attr_fullname(TelegramClient, name)
    await event.reply(
        f'Documentation for [{name}]({DOCS_CLIENT}{attr})',
        reply_to=event.reply_to_msg_id
    )

    # We have two @client.on, both could fire, stop stop that
    raise events.StopPropagation


# ============================== AutoReply ==============================
# ==============================  Helpers  ==============================


def search_attr(cls, query, threshold=0.6):
    seq = difflib.SequenceMatcher(b=query, autojunk=False)
    scores = []
    for n in dir(cls):
        if not n.startswith('_'):
            seq.set_seq1(n)
            scores.append((n, seq.ratio()))

    scores.sort(key=lambda t: t[1], reverse=True)
    if threshold is None:
        return scores[0]
    else:
        return scores[0][0] if scores[0][1] >= threshold else None


def attr_fullname(cls, n):
    m = getattr(cls, n)
    cls = sys.modules.get(m.__module__)
    for name in m.__qualname__.split('.')[:-1]:
        cls = getattr(cls, name)
    return cls.__module__ + '.' + cls.__name__ + '.' + m.__name__


# ==============================  Helpers  ==============================


bot.start(bot_token=os.environ['TG_TOKEN'])
bot.run_until_disconnected()
