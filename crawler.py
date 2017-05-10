# -*- coding: utf-8 -*-
import requests
import docker
import logging
from contextlib import contextmanager
import sys
import os
import time
from lxml import etree
import re
from urllib.parse import urlparse
import click
import csv
from target import Target
from time import sleep
import json

logger = logging.getLogger('crawler')
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%Y/%m/%d %H:%M:%S', filename="crawler.log")


def is_url_allowed(url, blacklist):
    for ft in blacklist:
        ft = re.compile(ft)
        if re.search(ft, url):
            return False

    return True

def get_charset(response):
    # Set default charset
    charset = 'utf8'

    m = re.findall(';charset=(.*)', response['mimeType'])
    if m:
        charset = m[0]

    return charset

@contextmanager
def start_splash():
    logger.debug("Starting splash")
    docker_cli = docker.from_env()
    while True:
        try:
            docker_cli.ping()
            break;
        except docker.errors.APIError:
            logger.critical("Can't connect to docker")
            click.echo("Look like docker hasn't started")
            sleep(10)

    if not docker_cli.containers.list(filters={'name':'splash'}, all=True):
        container = docker_cli.containers.create(
            image='scrapinghub/splash',
            ports={'5023': '5023',
                    '8050' : '8050',
                    '8051' : '8051'},
            name='splash')
    else:
        container = docker_cli.containers.get('splash')


    try:
        container.restart()
    except Exception as e:
        logger.critical(e)
        sys.exit(1)

    # Wait to container to start
    time.sleep(3)
    logger.debug("Splash started")

    yield

    # Container clean-up
    try:
        container.stop()
    except Exception as e:
        logger.warning("Exception while stop splash: %s, try to continue", e)


def get_har(url):
    page_url = '{}/render.har?url={}&wait=10&resource_timeout=30&timeout=60'.format(
        "http://localhost:8050", url
    )

    # try:
    #     with start_splash():
    #         res = requests.get(page_url)
    # except DockerStartError:
    #     logger.error(
    #         "There was an error running splash container. "
    #         "It's possible that previous splash container didn't finish well, "
    #         "please verify and stop any other splash instance to avoid port issues."
    #     )
    #     sys.exit(0)
    try:
        res = requests.get(page_url)
    except Exception as e:
        logger.warning("Fail to get har for url %s: %s", url, e)
        return None

    json_data = res.json()
 
    try:
        entries = json_data['log']['entries']
    except KeyError as e:
        logger.warning("Not expected answer from splash: %s, for %s", res.text, url)
        #sys.exit(1)
        return None 

    blacklist = ['.ttf', '.woff', 'fonts.googleapis.com', '^data:']

    logger.debug('[+] Detected %(n)d entries in HAR.', {'n': len(entries)})

    new_entries = []
    for entry in entries:
        entry_url = entry['request']['url']
        if not is_url_allowed(entry_url, blacklist):
            continue

        #response = entry['response']['content']

        #Some responses are empty, we delete them
        #if not response.get('text'):
        #    continue

        #charset = get_charset(response)
        #response['text'] = base64.b64decode(response['text']).decode(charset)
        new_entries.append(entry)

        logger.debug('[+] Added URL: %(url)s', {'url': entry_url})
        
    logger.debug('Returned %d entries for %s', len(new_entries), url)

    return new_entries

def load_filters(filters_file):
    filters = {line.split()[0]:line.split()[1] for line in filters_file.read().splitlines() if line[0] != '#'}
    return filters

def get_metrics(filters, hars, targets):
    result = {target:{key:False for key in filters.keys()} for target in targets}
    for i in range(len(hars)):
        if hars[i] != None:
            for entry in hars[i]:
                for filter_name, matcher in filters.items():
                    f = re.search(matcher, entry['request']['url'])
                    if f:
                        result[targets[i]][filter_name] = True
        else:
            for filter_name in filters:
                result[targets[i]][filter_name] = None
    return result

def get_all_hars(targets):
    hars = []
    logger.debug("Start crawling")
    with click.progressbar(targets, label='Crawling sites') as bar:
        for target in bar:    
            if target.url != None:
                logger.debug("Crawling %s", target.name)
                with start_splash():
                    har = get_har(target.url)
                    hars.append(har)
            else:
                logger.debug("Hasn't url for %s", target.name)
                hars.append(None)
    return hars

def get_rating(hars):
    rating = {}
    for har in hars:
        if har != None:
            try:
                target_url = har[0]['request']['url']
            except IndexError:
                logger.warning(har)
            for entry in har:
                url = entry['request']['url']
                if urlparse(url).netloc != urlparse(target_url).netloc:
                    if rating.get(urlparse(url).netloc.encode('utf8')) != None:
                        rating[urlparse(url).netloc.encode('utf8')] += 1
                    else:
                        rating[urlparse(url).netloc.encode('utf8')] = 1
    return rating

def save_results_csv(targets, metrics, filters_metrics):
    with open("result.csv", "w") as csvfile:
        fieldnames = ["name"] + list(filters_metrics.keys()) + ["url"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for target in targets:
            w = {"name": target.name, "url": target.url}
            w.update(metrics[target])
            writer.writerow(w) 
    
def print_rating(rating): 
    rating_view = [(value, key) for key, value in rating.items()]
    rating_view.sort(reverse=True)
    for value, key in rating_view:
        print("%s: %d" % (key, value))

def save_hars(hars):
    with open(".hars.save", "w") as save:
        save.write(json.dumps(hars, indent=2, ensure_ascii=False))

def load_hars():
    try:
        with open(".hars.save", "r") as save:
            return json.load(save)
    except IOError as e:
        logger.critical("Except while open save of hars: %s", e)
        exit(1)

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    '--debug',
    help='Include this flag to enable debug messages.',
    is_flag=True
)
@click.option(
    '--filters',
    type=click.File('r'),
    required=True,
    help='File with filters to find metrics.'
)   
@click.argument('targets_list', type=click.File('r'))
@click.option(
    '--offline', is_flag=True,
    help='Include this flag to load hars from save.'
)
def main(debug, targets_list, filters, offline):
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)
    
    targets = Target.load_list(targets_list) 

    filters_metrics = load_filters(filters)
    logger.debug("Load {} filters for metrics".format(len(filters_metrics)))

    if offline:
        hars = load_hars()
    else:
        hars = get_all_hars(targets)
        try:
            save_hars(hars)
        except Exception as e:
            logger.warning("Fail to backup hars: %s", e)

    rating = get_rating(hars)
    metrics = get_metrics(filters_metrics, hars, targets)
            
    save_results_csv(targets, metrics, filters_metrics)
    print_rating(rating)

if __name__ == "__main__":
    main()
