import urllib

from src.common.database import Database
from src.models.scraping import Scraping
from src.models.post import Post
from src.models.emailer import Emailer
import datetime
import uuid
import requests
from flask import Flask
from urlparse import urlparse
from bs4 import BeautifulSoup
import unidecode

class Pull(object):
    def __init__(self,
                 author_id,
                 type=None,
                 _id=None,
                 make="",
                 model="",
                 body_types="",
                 transmissions="",
                 min_price="",
                 max_price="",
                 min_kms="",
                 max_kms="",
                 min_year="",
                 max_year="",
                 mandatory_keywords="",
                 optional_keywords="",
                 kijiji_url="",
                 autotrader_url="",
                 created_date=(datetime.datetime.utcnow().strftime('%b, %d, %Y'))):
        self._id = uuid.uuid4().hex if _id is None else _id
        self.type = None if type is None else type
        self.author_id = author_id
        self.make = "" if make is "" else make
        self.model = "" if model is "" else model
        self.body_types = "" if body_types is "" else body_types
        self.transmissions = "" if transmissions is "" else transmissions
        self.min_price = "" if min_price is "" else min_price
        self.max_price = "" if max_price is "" else max_price
        self.min_kms = "" if min_kms is "" else min_kms
        self.max_kms = "" if max_kms is "" else max_kms
        self.min_year = "" if min_year is "" else min_year
        self.max_year = "" if max_year is "" else max_year
        self.mandatory_keywords = "" if mandatory_keywords is "" else mandatory_keywords
        self.optional_keywords = "" if optional_keywords is "" else optional_keywords
        self.kijiji_url = "" if kijiji_url is "" else kijiji_url
        self.autotrader_url = "" if autotrader_url is "" else autotrader_url
        self.created_date = created_date

    def generate_kijiji_url(self):
        database = Database()
        database.initialize()
        data = database.find_one(collection='scraping', query={})
        if self.body_types != "":
            url = data['scraping_dict'][self.make]['kijiji']['models'][self.model]['body_types'][self.body_types]
        else:
            url = data['scraping_dict'][self.make]['kijiji']['models'][self.model]['url']
        final_url = "http://www.kijiji.ca" + url
        trans_nums, trans_dict = [], {'manual': "1", 'automatic': "2", 'other': '3'}
        for trans in self.transmissions:
            trans_nums.append(trans_dict[trans.strip().lower()])
        payload = {
            'minPrice': self.min_price,
            'maxPrice': self.max_price,
            'attributeFiltersMin[caryear_i]': self.min_year,
            'attributeFiltersMax[caryear_i]': self.max_year,
            'keywords': self.mandatory_keywords,
            'transmission': '__'.join(trans_nums)
        }
        r = requests.get(final_url, params=payload)
        if any([(self.min_kms != ""), (self.max_kms != "")]):
            payload_kms = {
                'attributeFiltersMin[carmileageinkms_i]': min_kms,
                'attributeFiltersMax[carmileageinkms_i]': max_kms,
            }
            r_kms = requests.get(r.url, params=payload_kms)
            self.kijiji_url = r_kms.url
        else:
            self.kijiji_url = r.url

    def generate_autotrader_url(self):
        database = Database()
        database.initialize()
        data = database.find_one(collection='scraping', query={})
        base_url = data['scraping_dict'][self.make]['Autotrader']['models'][self.model]['url']
        try:
            trans_string = self.transmissions[0]
            for trans in ["," + i for i in self.transmissions[1:]]:
                trans_string += trans
        except IndexError:
            trans_string = None
        payload = {
            'body': self.body_types,
            'yRng': self.min_year + "," + self.max_year,
            'trans': trans_string,
            'pRng': self.min_price + "," + self.max_price,
            'oRng': self.min_kms + "," + self.max_kms
        }
        self.autotrader_url = requests.get(base_url, params=payload).url

    def generate_kijiji_posts_data(self, new_or_update):
        base = "https://www.kijiji.ca"
        new_posts, price_drops = [], []

        def generate_post_data(assigned_url, new_or_update):
            returning_new_posts, returning_price_drops = [], []
            request = requests.get(assigned_url)
            content = request.content
            soup = BeautifulSoup(content, "html.parser")
            link_soup = soup.findAll("div", {"class": "clearfix"})
            for link in link_soup:
                url_link = (link.find("a", {"class": "title enable-search-navigation-flag "}))
                if url_link is None:
                    continue
                else:
                    _id_html = (link.find("div", {"class": "watch watchlist-star p-vap-lnk-actn-addwtch"}))
                    url = base + url_link.get('href')
                    title = url_link.text.lstrip()
                    if "Wanted:" in title:
                        continue
                    image_html = (link.find("img", {"alt": title}))
                    image = image_html.get('src')
                    prices = []
                    prices.append((link.find("div", {"class": "price"})).text.lstrip().split("\n")[0])
                    date_posted = link.find("span", {"class": "date-posted"}).text.strip()
                    location_html = link.find("div", {"class": "location"})
                    location = location_html.text.strip().replace(date_posted, "")
                    if link.find("div", {"class": "dealer-logo-image"}) is None:
                        seller = "Owner"
                    else:
                        seller = "Dealer"
                    kms_trans_html = link.find("div", {"class": "details"})
                    try:
                        kms = (kms_trans_html.text.split("|")[1]).strip()
                    except IndexError:
                        kms = "N/A"
                    transmission = kms_trans_html.text.split("|")[0].strip()
                    description_html = link.find("div", {"class": "description"})
                    description = description_html.text.replace((transmission + " | " + kms), "").strip()
                    # Check for expired posts
                    request = requests.get(url)
                    content = request.content
                    soup = BeautifulSoup(content, "html.parser")
                    try:
                        _id = (_id_html.get('data-adid')).strip()
                        post = Post.from_mongo_post_id(_id)
                        if prices[0] != post.prices[0]:
                            print(prices[0])
                            print(post.prices[0])
                            prices = prices + post.prices
                            print(prices)
                            print(type(prices))
                            if new_or_update == 'update':
                                price_drops.append(post)
                        post.update_post({"_id": _id, "type": "kijiji", "location": location, "kms": kms, "image": image, "title": title, "date_posted": date_posted, "star": post.star,
                                          "hide": post.hide, "seller": seller, "prices": prices, "transmission": transmission, "description": description, "url": url, "pull_id": self._id})
                # If it doesn't exist, create it
                    except TypeError:
                        post = Post(_id=_id, type="kijiji", location=location, kms=kms, image=image, title=title, date_posted=date_posted, seller=seller,
                                    prices=prices, transmission=transmission, description=description, url=url, pull_id=self._id)
                        post.save_to_mongo()
                        if new_or_update == 'update':
                            new_posts.append(post)
            try:
                next_pge = soup.find("a", {"title": "Next"}).get('href')
                gen_new_posts, gen_price_drops = generate_post_data(base + next_pge)
                returning_new_posts = new_posts + gen_new_posts
                returning_price_drops = price_drops + gen_price_drops
            except AttributeError:
                return returning_new_posts, returning_price_drops

        returning_new_posts, returning_price_drops = generate_post_data(self.kijiji_url, new_or_update)
        print("price_drops: {}".format(returning_price_drops))
        print("new posts: {}".format(returning_new_posts))
        Emailer.send_email(self.author_id,  returning_new_posts, passed_msg='new_post')
        Emailer.send_email(self.author_id, returning_price_drops, passed_msg='price_drop')

    def generate_autotrader_posts_data(self, new_or_update):
        new_posts, price_drops = [], []
        session = Scraping.generate_session()
        request = session.get(self.autotrader_url)
        print(self.autotrader_url)
        if request.status_code != 200:
            print("autotrader_autotrader_posts_data() has returned a non-200 response code.")
            print("Status code: {}".format(request.status_code))
            print("Cookies: {}".format(session.cookies.get_dict))
            print("Url attempted: {}".format(self.autotrader_url))
        else:
            content = request.content
            soup = BeautifulSoup(content, "html.parser")
            results_count = int(soup.find("span", {"class": "at-results-count pull-left"}).text) + 1
            session.params = {"rcp": results_count}
            request = session.get(self.autotrader_url)
            content = request.content
            soup = BeautifulSoup(content, "html.parser")
            posts_soup = soup.findAll("div", {"class": lambda L: L and L.startswith('col-xs-12 result-item-inner')})
            for post in posts_soup:
                url_html = post.find("a", {"class": "main-photo click"})
                url = url_html.get('href')
                image = url_html.find("img").get("data-original")
                title = post.find("a", {"class": "result-title click"}).text.strip()
                try:
                    kms = post.find("div", {"class": "kms"}).text.strip()
                except AttributeError:
                    kms = "--"
                description = post.find("p", {"itemprop": "description"}).text.split('...')[0].strip().split("\n")[
                                  0] + "..."
                path = urlparse(url).path
                url_string = unidecode.unidecode(urllib.unquote_plus(path.encode('ascii')).decode('utf8'))
                location = ("{}, {}".format(url_string.split("/")[4].title(), url_string.split("/")[5].title()))
                _id = url.split("/")[6]
                url = "http://www.autotrader.ca/" + url
                prices = []
                prices.append(post.find("span", {"class": "price-amount"}).text)
                date_posted = "--"
                transmission = "--"
                seller_html = post.find("div", {"class": "seller-logo-container"}).findAll(
                    ("img", {"id": "imgDealerLogo",
                             "src": "/Images/Shared/blank.png",
                             "alt": lambda L: L and L.startswith('')}))
                if len(seller_html) == 0:
                    seller = "Owner"
                else:
                    seller = "Dealer"
            # Try to find the post in the database by _id
                try:
                    post = Post.from_mongo_post_id(_id)
                    if prices[0] != post.prices[0]:
                        print(prices[0])
                        print(post.prices[0])
                        prices = prices + post.prices
                        print(prices)
                        print(type(prices))
                        if new_or_update == 'update':
                            price_drops.append(post)
                    post.update_post(
                        {"_id": _id, "type": "autotrader", "location": location, "kms": kms, "image": image, "title": title,
                         "date_posted": date_posted, "star": post.star,
                         "hide": post.hide, "seller": seller, "prices": prices, "transmission": transmission,
                         "description": description, "url": url, "pull_id": self._id})
                # If it doesn't exist, create it
                except TypeError:
                    print("creating post... {}".format(urlparse(title)))
                    post = Post(_id=_id, type="autotrader", location=location, kms=kms, image=image, title=title,
                                date_posted=date_posted, seller=seller,
                                prices=prices, transmission=transmission, description=description, url=url,
                                pull_id=self._id)
                    post.save_to_mongo()
                    if new_or_update == 'update':
                        new_posts.append(post)
        print("price_drops: {}".format(price_drops))
        print("new posts: {}".format(new_posts))
        Emailer.send_email(self.author_id,  new_posts, passed_msg='new_post')
        Emailer.send_email(self.author_id, price_drops, passed_msg='price_drop')

    def delete_expired_posts(self):
        posts = Post.from_mongo(self._id)
        for post in posts:
            request = requests.get(post.url)
            content = request.content
            if post.type == "kijiji":
                soup = BeautifulSoup(content, "html.parser")
                expired_container = soup.find("div", {"class": "expired-ad-container"})
                if expired_container is not None:
                    post.delete_post()
            elif post.type == "autotrader":
                soup = BeautifulSoup(content, "html.parser")
                expired_container = soup.find("div", {"id": "pageNotFoundContainer"})
                if expired_container is not None:
                    post.delete_post()

    def save_to_mongo(self):
        Database.insert(collection='pulls', data=self.json())

    def json(self):
        return {"author_id": self.author_id,
                 "_id": self._id,
                 "type": self.type,
                 "make": self.make,
                 "model": self.model,
                 "body_types": self.body_types,
                 "transmissions": self.transmissions,
                 "min_price": self.min_price,
                 "max_price": self.max_price,
                 "min_kms": self.min_kms,
                 "max_kms": self.max_kms,
                 "min_year": self.min_year,
                 "max_year": self.max_year,
                 "mandatory_keywords": self.mandatory_keywords,
                 "optional_keywords": self.optional_keywords,
                 "kijiji_url": self.kijiji_url,
                 "autotrader_url": self.autotrader_url,
                 "created_date": self.created_date
        }

    @classmethod
    def from_mongo(cls, id):
        pull_data = Database.find_one(collection='pulls',
                                      query={'_id': id})
        return cls(**pull_data)
    # We've written this this way, so that we can later run
    # methods on the blog object we've returned.
    # @classmethod allows us to use 'cls' to return the class
    # we're currently working with, in case the class name ever
    # changes.

    @classmethod
    def find_by_author_id(cls, author_id):
        pulls = Database.find(collection="pulls",
                              query={"author_id": author_id})
        return [cls(**pull) for pull in pulls]
        # This will return blog objects in a list, using list comprehension.

    @classmethod
    def all_pulls(cls):
        pulls = Database.find(collection="pulls",
                              query={})
        return [cls(**pull) for pull in pulls]

    def update_pull(self, update):
        Database.update(collection="pulls", query={"_id": self._id}, update=update)
        Database.remove(collection="posts", query={"pull_id": self._id})
        return

    def delete_pull(self):
        Database.remove(collection="pulls", query={"_id": self._id})
        Database.remove_many(collection="posts", query={"pull_id": self._id})
        return


        @property
        def id(self):
            return self._id