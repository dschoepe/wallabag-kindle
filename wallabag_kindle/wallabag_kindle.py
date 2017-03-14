#!/usr/bin/env python3
import cgitb
import cgi
from configparser import ConfigParser
import html
import os
import os.path
import random
import string
import subprocess
import sys
import tempfile
import urllib.request
import urllib.parse
from urllib.parse import urljoin, urlencode
import json
import uwsgi

from ebooklib import epub
import ebooklib
from bs4 import BeautifulSoup


def die(msg):
    raise Exception(msg)

def info(msg):
    print(msg)

def load_config():
    config_parser = ConfigParser(allow_no_value = True)
    CONFIG_SECTION = 'wallabag-kindle'
    if 'configfile' not in uwsgi.opt:
        raise Exception('Location of config file not specified')
    cfg_loc = os.path.expanduser(uwsgi.opt['configfile'].decode('utf-8'))
    if os.path.isfile(cfg_loc):
        config_parser.read(cfg_loc)
    else:
        info("No config file found, creating default config")
        config_parser.add_section(CONFIG_SECTION)
        config_parser.set(CONFIG_SECTION, '# URL of wallabag instance')
        config_parser.set(CONFIG_SECTION, 'wb_url', "")
        config_parser.set(CONFIG_SECTION, '# clientid for the wallabag API')
        config_parser.set(CONFIG_SECTION, 'wb_client_id', '')
        config_parser.set(CONFIG_SECTION, '# clientsecret for the wallabag API')
        config_parser.set(CONFIG_SECTION, 'wb_client_secret', '')
        config_parser.set(CONFIG_SECTION, '# wallabag username')
        config_parser.set(CONFIG_SECTION, 'wb_user', '')
        config_parser.set(CONFIG_SECTION, '# wallabag password')
        config_parser.set(CONFIG_SECTION, 'wb_password', '')
        config_parser.set(CONFIG_SECTION, '# secret token for wallabag-kindle')
        new_token = ''.join(random.choice(string.ascii_letters + string.digits)\
                            for _ in range(32))
        config_parser.set(CONFIG_SECTION, 'secret_token', new_token)
        config_parser.set(CONFIG_SECTION, '# Your kindle address (e.g. foo@kindle.com)')
        config_parser.set(CONFIG_SECTION, 'kindle_address', '')
        config_parser.set(CONFIG_SECTION, '# URL to wallabag-kindle')
        config_parser.set(CONFIG_SECTION, 'wallabag_kindle_url', '')
        with open(cfg_loc, 'w') as cfg_handle:
            config_parser.write(cfg_handle)
    config = config_parser[CONFIG_SECTION]
    req_fields = ['wb_url', 'wb_client_id', 'wb_client_secret',
                  'wb_user', 'wb_password', 'secret_token',
                  'kindle_address', 'wallabag_kindle_url']
    for field in req_fields:
        if field not in config or config[field] == '':
            die("Required field %s missing in configuration" % field)
    return config

def get_wallabag_token(config):
    params = { 'username': config['wb_user'],
               'password': config['wb_password'],
               'client_id': config['wb_client_id'],
               'grant_type': 'password',
               'client_secret': config['wb_client_secret'] }
    req = urllib.request.Request(urllib.parse.urljoin(config['wb_url'],
                                                      "oauth/v2/token"),
                                 data=urllib.parse.urlencode(params).encode('utf-8'))
    resp = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
    return resp['access_token']

def replace_in_doc(config, doc):
    soup = BeautifulSoup(doc.get_content(), 'html.parser')
    print(type(doc.get_content()))
    for link in soup.find_all('a'):
        target = link['href']
        print(target)
        if target != "https://github.com/wallabag/wallabag/issues":
            new_target = urljoin(config['wallabag_kindle_url'],
                                 '?key=%s&action=add&url=%s' %
                                 (config['secret_token'],
                                  urllib.parse.quote_plus(target)))
            "%s/kindle/cgi-bin/add-to-wb.py?key=%s&url=%s" %\
                         (config['wb_url'],
                          config['secret_token'],
                          urllib.parse.quote(target))
            print("Replacing %s with %s" % (target, new_target))
            link['href'] = new_target
    doc.content = soup.encode(formatter=None)
    # print(soup.prettify(formatter=None))

def replace_links_in_file(config, f):
    book = epub.read_epub(f)
    for it in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        replace_in_doc(config, it)
    epub.write_epub(f, book, {})

def add_article(config, data, token):
    if 'url' not in data:
        return make_resp("No URL given")
    url = urllib.parse.unquote_plus(data['url'])
    url_encoded = html.escape(url)
    output = ["Original URL: <a href='"+url_encoded+"'>" + url_encoded +"</a>"]
    params = { 'url': url,
               'access_token': token }
    req = urllib.request.Request(urllib.parse.urljoin(config['wb_url'], 'api/entries.json'),
                                 data=urllib.parse.urlencode(params).encode('utf-8'))
    resp = urllib.request.urlopen(req)

    # wb.post_entries(url=url)
    output += ["Done, response code: %i<br/>" % resp.getcode()]
    return "<br/>".join(output).encode('utf-8')

def send_article(config, data, token):
    req_fields = ['article_id', 'article_title', 'article_url']
    for field in req_fields:
        if field not in data:
            return make_resp("Missing GET parameter: %s" % field)
    epub_in_file = tempfile.NamedTemporaryFile(delete=False, suffix='.epub')
    try:
        epub_in_file.close()
        epub_in = epub_in_file.name
        epub_url = urllib.parse.urljoin(
            config['wb_url'],
            '/api/entries/%s/export.epub?access_token=%s' %\
            (data['article_id'], token))
        # print(epub_url)
        urllib.request.urlretrieve(epub_url, epub_in)
        # Run it through ebook-convert once to ensure we get a valid epub:
        epub_file = tempfile.NamedTemporaryFile(delete=False, suffix='.epub')
        try:
            epub = epub_file.name
            epub_file.close()
            subprocess.call(['ebook-convert', epub_in, epub])
            replace_links_in_file(config, epub)
            mobi_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mobi')
            mobi = mobi_file.name
            try:
                mobi_file.close()
                # Turn into mobi and set some metadata:
                subprocess.call(['ebook-convert', epub, mobi,
                                 '--title', data['article_title'],
                                 '--authors', data['article_url']])
                # Send it off to the kindle address:
                subprocess.call(['mpack', '-s', 'Wallabag Article',
                                 mobi, config['kindle_address']])
                return make_resp('article sent')
            finally:
                os.remove(mobi)
        finally:
            os.remove(epub)
    finally:
        os.remove(epub_in)

def make_resp(msg):
    return [msg.encode('utf-8')]

def application(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/html')])
    config = load_config()
    data = urllib.parse.parse_qs(environ['QUERY_STRING'])
    for key, val in data.items():
        if len(val) != 1:
            die("multiple values for parameter %s" % key)
        data[key] = val[0]
    if 'key' not in data:
        return make_resp("Invalid key")
    key = data['key']
    if key != config['secret_token']:
        return make_resp("Invalid key")
    if 'action' not in data:
        return make_resp('No action specified')
    action = data['action']
    token = get_wallabag_token(config)
    if action == 'add':
        return add_article(config, data, token)
    elif action == 'send':
        return send_article(config, data, token)
    else:
        return make_resp("Unknown action %s" % action)
