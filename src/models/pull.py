from DateTime import DateTime
from src.common.database import Database
from src.models.scraping import Scraping
from src.models.post import Post
from src.models.emailer import Emailer
import datetime
import uuid
import requests
from flask import session
from bs4 import BeautifulSoup

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
                 url="",
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
        self.url = "" if url is "" else url
        self.created_date = created_date

    def generate_url(self):
        base = "https://www.kijiji.ca/b-cars-trucks/ontario/"

        def parse_model(url):
            split = url.split("ontario/")
            return (split[1]).split("-", 1)
        final_url, body_types_len, count = "", len(self.body_types), 0
        data = Scraping.dict_from_mongo()
        if len(self.body_types) > 0:
            for body_type in self.body_types:
                count += 1
                result = parse_model(data[self.make][self.model]['body_types'][body_type])
                if body_types_len == 1:
                    final_url = final_url + (result[0] + "-" + result[1])
                else:
                    if count != body_types_len:
                        if count == 1:
                            final_url = final_url + result[0]
                        else:
                            final_url = final_url + ("__" + result[0])
                    elif count == body_types_len:
                        final_url = final_url + ("__" + result[0] + "-" + result[1])
        else:
            result = (data[self.make][self.model]['URL']).split("ontario/")
            final_url = result[1]
        final_url = base + final_url
        payload = {
            'minPrice': self.min_price,
            'maxPrice': self.max_price,
            'attributeFiltersMin[caryear_i]': self.min_year,
            'attributeFiltersMax[caryear_i]': self.max_year,
            'keywords': self.mandatory_keywords
        }
        payload_kms = {
            'attributeFiltersMin[carmileageinkms_i]': self.min_kms,
            'attributeFiltersMax[carmileageinkms_i]': self.max_kms,
        }
        r = requests.get(final_url, params=payload)
        r_kms = requests.get(r.url, params=payload_kms)
        if self.transmissions != "":
            if len(self.transmissions) == 1:
                trans_num = data[self.make][self.model]['transmissions'][self.transmissions[0]]
                final_url = str(r_kms.url) + "&transmission=" + str(trans_num)
            else:
                count = 0
                for transmission in self.transmissions:
                    trans_num = data[self.make][self.model]['transmissions'][transmission]
                    count += 1
                    if count == 1:
                        final_url = str(r_kms.url) + "&transmission=" + str(trans_num)
                    else:
                        final_url = final_url + "__" + str(trans_num)
        self.url = final_url

    def generate_posts_data(self, new_or_update):
        base = "https://www.kijiji.ca"
        new_posts = []
        price_drops = []

        def generate_post_data(assigned_url, new_or_update):
            new_posts = []
            price_drops = []
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
                    price = (link.find("div", {"class": "price"})).text.lstrip().split("\n")[0]
                    prices = []
                    prices.append(price)
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
                            prices = prices + post.prices
                            if new_or_update == 'update':
                                price_drops.append(post)
                        post.update_post({"_id": _id, "type": "autos", "location": location, "kms": kms, "image": image, "title": title, "date_posted": date_posted,
                                          "seller": seller, "prices": prices, "transmission": transmission, "description": description, "url": url, "pull_id": self._id})
                # If it doesn't exist, create it
                    except TypeError:
                        post = Post(_id=_id, type="autos", location=location, kms=kms, image=image, title=title, date_posted=date_posted, seller=seller,
                                    prices=prices, transmission=transmission, description=description, url=url, pull_id=self._id)
                        post.save_to_mongo()
                        if new_or_update == 'update':
                            new_posts.append(post)
            try:
                next_pge = soup.find("a", {"title": "Next"}).get('href')
                gen_new_posts, gen_price_drops = generate_post_data(base + next_pge)
                new_posts = new_posts + gen_new_posts
                price_drops = price_drops + gen_price_drops
            except AttributeError:
                return new_posts, price_drops

        gen_new_posts, gen_price_drops = generate_post_data(self.url, new_or_update)
        new_posts = new_posts + gen_new_posts
        price_drops = price_drops + gen_price_drops
        Emailer.send_email(self.author_id, new_posts, passed_msg='new_post')
        Emailer.send_email(self.author_id, price_drops, passed_msg='price_drop')

    def delete_expired_posts(self):
        posts = Post.from_mongo(self._id)
        for post in posts:
            request = requests.get(post.url)
            content = request.content
            soup = BeautifulSoup(content, "html.parser")
            expired_container = soup.find("div", {"class": "expired-ad-container"})
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
                 "url": self.url,
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