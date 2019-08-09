from selenium import webdriver
from datetime import date, timedelta
import time
import logging
import argparse
import getpass
from builtins import input
import unidecode
import re
import os

log = logging.getLogger(__name__)


def scrape_loop(query, since_date, until_date, delta_days=30, wait_secs=5, username="", password=""):
    tweet_ids = set()

    log.info("Scrape Loop %s since %s until %s", query, since_date, until_date)

    driver = webdriver.Chrome()
    driver.implicitly_wait(wait_secs)

    if username and password:
        try:
            log.info("Attempting to log in as %s", username)
            driver.get('https://twitter.com/explore')
            driver.find_element_by_id("signin-link").click()
            username_field = driver.find_element_by_name("session[username_or_email]")
            password_field = driver.find_element_by_name("session[password]")
            username_field.send_keys(username)
            password_field.send_keys(password)
            form = driver.find_element_by_css_selector('[data-component="login_callout"]')
            form.submit()
            log.info("Login Success!")
        except:
            log.error("Failed to log in as %s, trying to continue anyway!", username)
            pass

    for new_since_date, new_until_date in _next_dates(since_date, until_date, delta_days):
        new_tweet_ids = set()
        try:
            new_tweet_ids = scrape(driver, query, new_since_date, new_until_date, wait_secs)

            with open(slugify(query)+".tmp", 'a') as f:
                for tweet_id in new_tweet_ids:
                    f.write(tweet_id + '\n')

            tweet_ids.update(new_tweet_ids)
        except:
            log.error("Failed to load q={} since:{} until:{} search results!", query, new_since_date, new_until_date)
            pass
        log.info("Found %s tweet ids for a total of %s unique tweet ids", len(new_tweet_ids), len(tweet_ids))

    driver.close()
    driver.quit()

    return tweet_ids


def _next_dates(since_date, until_date, delta_days):
    last_date = False
    new_since_date = until_date
    while not last_date:
        new_until_date = new_since_date
        new_since_date = new_since_date - timedelta(days=delta_days)
        if new_since_date <= since_date:
            new_since_date = since_date
            last_date = True
        yield new_since_date, new_until_date


def scrape(driver, query, since_date, until_date, wait_secs):
    log.info("Scraping %s since %s until %s", query, since_date, until_date)
    
    url = "https://twitter.com/search?q={}%20since%3A{}%20until%3A{}&src=typed_query&f=live".format(query, since_date.isoformat(), until_date.isoformat())
    
    log.debug("Getting %s", url)

    driver.get(url)

    scroll_count = 0
    last_tweet_count = 0
    
    while last_tweet_count != len(driver.find_elements_by_class_name("original-tweet")):
        scroll_count += 1
        last_tweet_count = len(driver.find_elements_by_class_name("original-tweet"))
        log.debug("Scrolling down %s. Found %s tweets.", scroll_count, last_tweet_count)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_secs)

    temp_folder = "scrape/{}".format(slugify(query))
    os.makedirs(temp_folder, exist_ok=True)
    temp_file = "{}/{}_{}_{}.html".format(temp_folder, slugify(query), since_date.isoformat(), until_date.isoformat())
    with open(temp_file, 'w') as f:
        f.write(driver.page_source)

    time.sleep(1)

    return set([e.get_attribute("data-tweet-id") for e in driver.find_elements_by_class_name("original-tweet")])


def _to_date(date_str):
    date_split = date_str.split("-")
    return date(int(date_split[0]), int(date_split[1]), int(date_split[2]))


def slugify(query):
    query = unidecode.unidecode(query).lower()
    return re.sub(r'[\W_]+', '_', query)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--since", default=(date.today() - timedelta(days=1)).isoformat(), help="Tweets since this date. Default is 1 day ago")
    parser.add_argument("--until", default=date.today().isoformat(), help="Tweets until this date. Default is today.")
    parser.add_argument("--delta-days", type=int, default=1, help="Number of days to include in each search.")
    parser.add_argument("--wait-secs", type=int, default=3, help="Number of seconds to wait between each scroll.")
    parser.add_argument("--login", action='store_true', help="Attempt log in using your Twitter account.")
    parser.add_argument("--debug", action="store_true")
    parser.set_defaults(login=False,debug=True)
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG if args.debug else logging.INFO)
    logging.getLogger("selenium").setLevel(logging.WARNING)

    if (args.login):
        username = input("Enter Twitter username: ")
        password = getpass.getpass("Enter Twitter password: ")
    else:
        username = ""
        password = ""

    main_tweet_ids = scrape_loop(args.query, _to_date(args.since), _to_date(args.until),
                                 delta_days=args.delta_days, wait_secs=args.wait_secs,
                                 username=username, password=password)
    for tweet_id in main_tweet_ids:
        print(tweet_id)
    log.info("Found %s unique tweet ids", len(main_tweet_ids))
