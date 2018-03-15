import requests
from bs4 import BeautifulSoup
import uuid
import datetime
from src.common.database import Database
from inspect import getmembers
from pprint import pprint


class Post(object):
    def __init__(self, _id=None, type=None, location=None, kms=None, image=None, title=None, date_posted=None, star=False,
                 hide=False, prices=None, transmission=None, description=None, url=None, pull_id=None, seller="Dealer",):
        self._id = None if _id is None else _id
        self.type = None if type is None else type
        self.pull_id = None if pull_id is None else pull_id
        self.url = None if url is None else url
        self.title = None if title is None else title
        self.image = None if image is None else image
        self.prices = None if prices is None else prices
        self.location = None if location is None else location
        self.date_posted = None if date_posted is None else date_posted
        self.star = False if star is False else star
        self.hide = False if hide is False else hide
        self.kms = None if kms is None else kms
        self.transmission = None if transmission is None else transmission
        self.description = None if description is None else description
        self.seller = "Dealer" if seller is "Dealer" else seller

    def json(self):
        return {"_id": self._id,
                "type": self.type,
                "pull_id": self.pull_id,
                "url": self.url,
                "image": self.image,
                "prices": self.prices,
                "title": self.title,
                "location": self.location,
                "star": self.star,
                "hide": self.hide,
                "date_posted": self.date_posted,
                "kms": self.kms,
                "transmission": self.transmission,
                "description": self.description,
                "seller": self.seller
        }

    def save_to_mongo(self):
        Database.insert(collection='posts', data=self.json())

    @classmethod
    def from_mongo(cls, pull_id):
        posts = Database.find(collection='posts',
                              query={'pull_id': pull_id})
        return [cls(**post) for post in posts]

    @classmethod
    def from_mongo_post_id(cls, post_id):
        post = Database.find_one(collection='posts',
                              query={'_id': post_id})
        return cls(**post)

    def update_post(self, update):
        Database.update(collection="posts", query={"_id": self._id}, update=update)

    @classmethod
    def get_starred_posts(cls, pull_id):
        posts = Database.find(collection='posts',
                                 query={'pull_id': pull_id, 'star': True})
        return [cls(**post) for post in posts]

    def delete_post(self):
        Database.remove(collection="posts", query={"_id": self._id})
        return
