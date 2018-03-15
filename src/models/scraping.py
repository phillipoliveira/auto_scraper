import uuid
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from src.common.database import Database
import datetime


class Scraping(object):
    def __init__(self, _id=None, scraping_dict=None, created_date=None):
        self._id = uuid.uuid4().hex if _id is None else _id
        self.scraping_dict = self.build_main_dict() if scraping_dict is None else scraping_dict
        self.created_date = datetime.datetime.utcnow() if created_date is None else created_date

    @staticmethod
    def generate_session():
        session = requests.session()
        session.params = ({"prv": "Ontario",
                           "loc": "M8Y,0A4"})
        # FOR AUTOTRADER - POSTAL CODE GOES HERE
        headers = {
            "Connection": "close",  # another way to cover tracks
            "User-Agent": UserAgent().random}
        session.headers = headers
        return session

    @classmethod
    def autotrader_makes(cls):
        session = cls.generate_session()
        request = session.get("http://www.autotrader.ca/cars/")
        if request.status_code != 200:
            print("autotrader_makes() has returned a non-200 response code.")
            print("Status code: {}".format(request.status_code))
            print("Cookies: {}".format(session.cookies.get_dict))
            print("Url attempted: {}".format("http://www.autotrader.ca/cars/"))
        content = request.content
        soup = BeautifulSoup(content, "html.parser")
        link_soup = soup.findAll("a",
                                 {"id": lambda L: L and L.startswith('ctl00_ctl00_MainContent_MainContent_dlAllMakes')})
        makes = {}
        for link in link_soup:
            url = link.get('href')
            if link.text == 'American Motors (AMC)':
                makes['AMC'] = url
            elif link.text == 'CADILLAC':
                makes['Cadillac'] = url
            elif link.text == 'Hummer':
                makes['HUMMER'] = url
            elif link.text == 'TESLA':
                makes['Tesla'] = url
            elif link.text == 'smart':
                makes['Smart'] = url
            else:
                makes[link.text] = url
        return makes

    @staticmethod
    def kijiji_makes():
        request = requests.get("https://www.kijiji.ca/b-cars-trucks/ontario/c174l9004")
        content = request.content
        soup = BeautifulSoup(content, "html.parser")
        # Get the /b-cars-trucks/ontario/c174l9004 html
        link_soup = soup.findAll("a", {"class": "attribute-selected", "data-event": "carmakeSelection"})
        # Find the html with all the 'makes' links
        makes = {}
        for link in link_soup:
            makes[(link.get_text().lstrip())] = (str(link.get('href')))
        # Build a dictionary with makes and their associated URLs
        return makes

    @classmethod
    def kijiji_models(cls, make_url):
        request = requests.get("https://www.kijiji.ca" + str(make_url))
        content = request.content
        soup = BeautifulSoup(content, "html.parser")
        # Scrap the page associated with the make url passed
        models = {}
        model_soup = soup.findAll("a", {"class": "attribute-selected", "data-event": "carmodelSelection"})
        # Find the html with the models
        if len(model_soup) == 0:
            url = make_url
            body_types, transmissions = cls.kijiji_body_type_trans(url)
            # If kijiji returns no models, that means there's none in any ad entries (Austin-Healy)
            models["All"] = {"url": url,
                             "transmissions": transmissions,
                             "body_types": body_types}
        else:
            for link in model_soup:
                url = str(link.get('href'))
                body_types, transmissions = cls.kijiji_body_type_trans(url)
                # Using the kijiji_body_type_trans(url) function, build a dictionary with that makes URL,
                # datavalues for each transmission, and urls for each bodytype
                model_text = link.get_text().lstrip()
                print(model_text)
                # We need to replace periods with underscores, because JSON doesn't support periods. We NEED to revert this on
                # when we build out model lists later
                if "bmw" in make_url.lower():
                    model_text = model_text.replace("-", " ").upper()
                else:
                    model_text = model_text.replace(".", "_").upper()
                models[model_text] = {"url": url,
                                      "transmissions": transmissions,
                                      "body_types": body_types}
        return models

    @classmethod
    def autotrader_models(cls, url):
        session = cls.generate_session()
        url = "http://www.autotrader.ca" + url
        request = session.get(url)
        if request.status_code != 200:
            print("autotrader_models() has returned a non-200 response code.")
            print("Status code: {}".format(request.status_code))
            print("Cookies: {}".format(session.cookies.get_dict))
            print("Url attempted: {}".format(url))
        content = request.content
        soup = BeautifulSoup(content, "html.parser")
        link_soup = soup.find("ul", {"id": "rfModel"})
        models_soup = link_soup.findAll("li", {"data-dropdownvalue": lambda L: L and L.startswith('')})
        models = {}
        for model in models_soup:
            print(model.text)
            url_parts = url.split("/?hprc=")
            model_encoding = (model.get('data-dropdownvalue')).encode('utf-8').strip().replace(" ", "%20").replace("/",
                                                                                                                   "_")
            model_url = url_parts[0] + "/" + model_encoding.decode('utf-8').lower() + "/?hprc=" + url_parts[1]
            body_styles, transmissions = cls.autotrader_body_type_trans(model_url)
            # We need to replace periods with underscores, because JSON doesn't support periods. We NEED to revert this on
            # when we build out model lists later
            if model.text.split(" (").strip() == "Unspecified":
                model_text = "OTHER"
            else:
                model_text = model.text.split(" (")[0].replace(".", "_").upper()
            models[model_text] = {"url": model_url,
                                  "body_styles": body_styles,
                                  "transmissions": transmissions}
        return models

    @staticmethod
    def kijiji_body_type_trans(model_url):
        request = requests.get("https://www.kijiji.ca" + str(model_url))
        content = request.content
        soup = BeautifulSoup(content, "html.parser")
        body_types, transmissions = {}, {}
        # Scrap the model page
        for link in soup.findAll("a", {"class": "attribute-selected", "data-event": "carbodytypeSelection"}):
            body_types[(link.get_text().lstrip()).split(" (")[0]] = (str(link.get('href')))
        # Build a dictionary with body_type names and urls
        for link in soup.findAll("a", {"class": "attribute-selected", "data-event": "cartransmissionSelection"}):
            transmissions[(link.get_text().lstrip())] = str(link.get('data-id'))
        # Build a dictionary with transmission names and datavalues
        return body_types, transmissions

    @classmethod
    def autotrader_body_type_trans(cls, model_url):
        session = cls.generate_session()
        request = session.get(model_url)
        if request.status_code != 200:
            print("autotrader_body_type_trans() has returned a non-200 response code.")
            print("Status code: {}".format(request.status_code))
            print("Cookies: {}".format(session.cookies.get_dict))
            print("Url attempted: {}".format(model_url))
        content = request.content
        soup = BeautifulSoup(content, "html.parser")
        body_styles_soup = soup.find("ul", {"id": "rfBodyStyle"})
        body_styles_links = body_styles_soup.findAll("li", {"data-count": lambda L: L and L.startswith('')})
        trans_soup = soup.find("ul", {"id": "fbTransmission"})
        trans_links = trans_soup.findAll("input")
        body_styles, transmissions = {}, {}
        for link in body_styles_links:
            if link.get('data-dropdownvalue') == "Other/Don't Know":
                body_styles["Other"] = link.get('data-dropdownvalue')
            else:
                body_styles[link.text.split(" (")[0]] = link.get('data-dropdownvalue')
        for link in trans_links:
            if link.get('data-value') == "Other/Don't Know":
                transmissions["Other"] = link.get('data-value')
            else:
                transmissions[link.get('data-value')] = link.get('data-value')
        return body_styles, transmissions

    @classmethod
    def build_main_dict(cls):
        t0 = datetime.datetime.utcnow()
        main_dict = {}
        autotrader_makes_dict = cls.autotrader_makes()
        while autotrader_makes_dict is None:
            autotrader_makes_dict = cls.autotrader_makes()
        kijiji_makes_dict = cls.kijiji_makes()
        # Assign kijiji and autotrader 'makes' to dictionary object
        autotrader_makes_set = set(autotrader_makes_dict.keys())
        # Form sets with the keys in each dictionary
        kijiji_makes_set = set(kijiji_makes_dict.keys())
        kijiji_only = kijiji_makes_set.difference(autotrader_makes_set)
        # Create a set with kijiji-only makes
        print("Kijiji only: {}".format(kijiji_only))
        autotrader_only = autotrader_makes_set.difference(kijiji_makes_set)
        # Create a set with autotrader-only makes
        print("Autotrader only: {}".format(autotrader_only))
        all_makes = autotrader_makes_set.intersection(kijiji_makes_set)
        # Create a set with makes found on both platforms
        print("The rest: {}".format(all_makes))
        for make in all_makes:
            main_dict[make] = {
                "kijiji":
                    {"url": kijiji_makes_dict[make],
                     "models": cls.kijiji_models((kijiji_makes_dict[make]))
                     },
                "Autotrader":
                    {"url": autotrader_makes_dict[make],
                     "models": cls.autotrader_models((autotrader_makes_dict[make]))
                     }
            }
            print(make)
        # Add an entry to the main_dict, with a singular make and child dictionaries for autotrader and kijiji content
        #        pprint.pprint(main_dict)
        for kijiji_make in kijiji_only:
            main_dict[kijiji_make] = {
                "Kijiji":
                    {"url": kijiji_makes_dict[kijiji_make],
                     "models": cls.kijiji_models((kijiji_makes_dict[kijiji_make]))
                     }
            }
            # Add an entry to the main_dict for makes that only exist in kijiji
            print(kijiji_make)
        for autotrader_make in autotrader_only:
            main_dict[autotrader_make] = {
                "Autotrader":
                    {"url": autotrader_makes_dict[autotrader_make],
                     "models": cls.autotrader_models((autotrader_makes_dict[autotrader_make]))
                     }
            }
            # Add an entry to the main_dict for makes that only exist in autotrader
            print(autotrader_make)
        t1 = datetime.datetime.utcnow()
        print("This took: {}".format(t1 - t0))
        return main_dict

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
            "scraping_dict": self.scraping_dict,
            "created_date": self.created_date
        }

    @classmethod
    def dict_from_mongo(cls):
        data = Database.find_one("scraping", {})
        return data

    @classmethod
    def get_models(cls, make):
        data = cls.dict_from_mongo()
        try:
            autotrader_models_set = list(data["scraping_dict"][make]["kijiji"]['models'].keys())
        except KeyError:
            autotrader_models_set = []
        try:
            kijiji_models_set = list(data["scraping_dict"][make]["Autotrader"]['models'].keys())
        except KeyError:
            kijiji_models_set = []
        models = set(kijiji_models_set + autotrader_models_set)
        clean_models = []
        for i in models:
            clean_models.append(i.replace("_", "."))
        return list(sorted(clean_models))

    @classmethod
    def get_body_types_trans(cls, make, model):
        data = cls.dict_from_mongo()
        try:
            autotrader_body_types_set = set(
                data["scraping_dict"][make]["Autotrader"]['models'][model]['body_styles'].keys())
            autotrader_trans_set = set(
                data["scraping_dict"][make]["Autotrader"]['models'][model]['transmissions'].keys())
        except KeyError:
            autotrader_body_types_set = set()
            autotrader_trans_set = set()
        try:
            kijiji_body_types_set = set(data["scraping_dict"][make]["kijiji"]['models'][model]['body_types'].keys())
            kijiji_trans_set = set(data["scraping_dict"][make]["kijiji"]['models'][model]['transmissions'].keys())
        except KeyError:
            kijiji_body_types_set = set()
            kijiji_trans_set = set()
        if any([(len(kijiji_body_types_set) == 0), (len(autotrader_body_types_set) == 0)]):
            body_types = kijiji_body_types_set.union(autotrader_body_types_set)
            trans = kijiji_trans_set.union(autotrader_trans_set)
        else:
            body_types = kijiji_body_types_set.intersection(autotrader_body_types_set)
            trans = kijiji_trans_set.intersection(autotrader_trans_set)
        return body_types, trans

