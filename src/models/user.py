import hashlib
from src.common.database import Database
from flask import Flask, session
import datetime
import uuid


class User(object):
    def __init__(self, email, password, _id=None, new_post_email=True, price_drop_email=True):
        self.email = email
        self.password = password
        self.new_post_email = True if new_post_email is None else True
        self.price_drop_email = True if price_drop_email is None else True
        self._id = uuid.uuid4().hex if _id is None else _id

    @classmethod
    def get_by_email(cls, email):
        data = Database.find_one("users", {"email": email})
        if data is not None:
            return cls(**data)
    # Why is this a class method? If we're getting a user by email, we
    # won't have their user object at that time, so we need to find the
    # user object and return it.

    @classmethod
    def get_by_id(cls, _id):
        data = Database.find_one("users", {"_id": _id})
        if data is not None:
            return cls(**data)

    @staticmethod
    def login_valid(email, password):
        # check whether a user's email matches the password they sent us.
        user = User.get_by_email(email)
        if user is not None:
            # Check the password:
            return user.password == password
        else:
            return False

    @classmethod
    def register(cls, email, password):
        user = cls.get_by_email(email)
        if user is None:
            # User doesn't exist, we can create it.
            new_user = cls(email, password)
            new_user.save_to_mongo()
            session['email'] = email
            return True
        else:
            # user exists
            return False
        # We're using @classmethod, so that if the name of the class changes,
        # we don't need to modify the function

    @staticmethod
    def login(user_email):
        # login valid has already been called
        session['email'] = user_email

    @staticmethod
    def logout():
        session['email'] = None

    def json(self):
        return {
            "email": self.email,
            "_id": self._id,
            "password": self.password,
            "new_post_email": self.new_post_email,
            "price_drop_email": self.price_drop_email
        }
    # Because this JSON method is sending passwords, it is NOT SAFE
    # to be sent over a network

    def save_to_mongo(self):
        Database.insert(collection="users", data=self.json())

    @property
    def id(self):
        return self._id