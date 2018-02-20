import requests
from bs4 import BeautifulSoup
import uuid
import datetime
from src.common.database import Database
from inspect import getmembers
from pprint import pprint



class Scraping(object):
    def __init__(self, _id=None, scraping_dict=None, created_date=None):
        self._id = uuid.uuid4().hex if _id is None else _id
        self.scraping_dict = self.build_scraping_dict() if scraping_dict is None else scraping_dict
        self.created_date = datetime.datetime.utcnow() if created_date is None else created_date


    @staticmethod
    def get_makes():
        request = requests.get("https://www.kijiji.ca/b-cars-trucks/ontario/c174l9004")
#        pprint(getmembers(request.headers))
        content = request.content
        soup = BeautifulSoup(content, "html.parser")
        link_soup = soup.findAll("a", {"class": "attribute-selected", "data-event": "carmakeSelection"})
        makes = {}
        for link in link_soup:
            makes[(link.get_text().lstrip())] = (str(link.get('href')))
        return makes

        # <ul data-menuid="carmake_s"> </ul>

    def get_models(self, make_url):
        request = requests.get("https://www.kijiji.ca" + str(make_url))
        content = request.content
        soup = BeautifulSoup(content, "html.parser")
        models = {}
        for link in soup.findAll("a", {"class": "attribute-selected", "data-event": "carmodelSelection"}):
            models[(link.get_text().lstrip())] = (str(link.get('href')))
        return models

    def get_body_type_trans(self, model_url):
            request = requests.get("https://www.kijiji.ca" + str(model_url))
            content = request.content
            soup = BeautifulSoup(content, "html.parser")
            body_types, transmissions = {}, {}
            for link in soup.findAll("a", {"class": "attribute-selected", "data-event": "carbodytypeSelection"}):
                body_types[(link.get_text().lstrip())] = (str(link.get('href')))
            for link in soup.findAll("a", {"class": "attribute-selected", "data-event": "cartransmissionSelection"}):
                transmissions[(link.get_text().lstrip())] = (str(link.get('href'))[-1:])
            return body_types, transmissions

    def build_scraping_dict(self):
        Database.initialize()
        main_dict = {}
        start = datetime.datetime.utcnow()
        try:
            count = 0
            for make_key, make_value in self.get_makes().items():
                count += 1
                print(make_key+make_value+" {}/852".format(count))
                main_dict[make_key] = {"URL": make_value}
                for model_key, model_value in self.get_models(make_value).items():
                    count += 1
                    print("\t" + model_key+" {}/852".format(count))
                    body_types, transmissions = self.get_body_type_trans(model_value)
                    main_dict[make_key][(model_key.replace(".", ","))] = {"URL": model_value,
                                                                          "body_types": body_types,
                                                                          "transmissions": transmissions}
            print("This took: {}".format((datetime.datetime.utcnow()) - start))
            return main_dict
        except requests.exceptions.ConnectionError:
            print("Connection refused")

    def save_to_mongo(self):
        Database.insert(collection='scraping', data=self.json())
    #    "https://www.kijiji.ca/b-cars-trucks/ontario/+" + make + model + \
    #    "/c174l9004a54a1000054?price-type=fixed&price=" + min_price + "__4000" + max_price + \
    #    "&kilometers=" + min_kms + "__" + max_kms&transmission=" + trans_option

    def update_mongo(self):
        Database.update(collection='scraping', query={"_id": self._id}, update=self.json())

    def json(self):
        return {
            "_id": self._id,
            "scraping_dict": self.scraping_dict
        }

    @classmethod
    def dict_from_mongo(cls):
        data = Database.find_one("scraping", {})
        dict = data['scraping_dict']
        return dict

