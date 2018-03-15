from flask import Flask, render_template, session, make_response, request
from src.common.database import Database
from src.models.user import User
from src.models.pull import Pull
from src.models.scraping import Scraping
from src.models.post import Post
from src.models.scheduledtasks import ScheduledTasks
import hashlib
import re

app = Flask(__name__)
app.secret_key = "miata"


@app.route('/')
# Returns the home page
def home_template():
    try:
        if session['email'] is not None:
            return make_response(start_pull())
    except KeyError:
        return render_template('login.html')


@app.route('/login')
# Returns the login page
def login_template():
    return render_template('login.html')

@app.route('/register')
# Returns the registration page
def register_template():
    return render_template('register.html')

@app.before_first_request
def initialize_database():
    Database.initialize()


@app.route('/auth/login', methods=['POST', 'GET'])
# Login endpoint - this endpoint only accepts POST requests
def login_user():
    if request.method == 'GET':
        if session['email'] is None:
            return make_response(home_template())
        else:
            return make_response(start_pull())

    else:
        email = request.form['email']
        password = request.form['password']
        hash_pass = hashlib.sha256(password.encode()).hexdigest()
        # this will get the info submitted into the base.html page.
        if User.login_valid(email, hash_pass):
            User.login(email)
            return make_response(start_pull())
        else:
            session['email'] = None
            return render_template('login.html')

@app.route('/auth/register', methods=['POST', 'GET'])
# Register endpoint:
def register_user():
  if request.method == 'GET':
    if session['email'] is None:
        return make_response(home_template())
    else:
        return make_response(start_pull())
  else:
    email = request.form['email']
    password = request.form['password']
    if not all([(re.match(r"^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$", email)), (len(password) > 7)]):
      msg = "All users must have a valid email,\nand a password with a minimum of 8 characters."
      session['email'] = None
      return render_template('register.html', msg=msg)
    else:
      if Database.find_one("users", {"email": email}) is None:
        hash_pass = hashlib.sha256(password.encode()).hexdigest()
        # Get the user's credentials
        User.register(email, hash_pass)
        user = User.get_by_email(email)
        #scraping = Scraping()
        #scraping.save_to_mongo()
        # Register the user using the method in the User object. This sets the session email, and saves the user to Mongo.
        return make_response(start_pull())
      else:
        msg = """This email address is already in use. <a href="/login">Already have an account?</a>"""
        return render_template('register.html', msg=msg)


@app.route('/pulls')
# Returns the registration page
def start_pull():
    user = User.get_by_email(session['email'])
    pulls = Pull.find_by_author_id(user.id)
    return render_template('pulls.html', pulls=pulls)


@app.route('/pulls/make/<string:pull_id>')
# Returns the registration page
def pull_make(pull_id):
    data = Scraping.dict_from_mongo()
    makes = sorted(data['scraping_dict'].keys())
    return render_template('pulls-make.html', makes=makes, pull_id=pull_id)


@app.route('/pulls/model/<string:pull_id>')
# Returns the registration page
def pull_model(pull_id):
    make = request.args.get('make')
    models = Scraping.get_models(make)
    return render_template('pulls-model.html', make=make, models=models, pull_id=pull_id)


@app.route('/pulls/body_type/<string:make>/<string:pull_id>')
# Returns the registration page
def pull_body_type(make, pull_id):
    model = request.args.get('model')
    model = model.replace(".", "_")
    print(model)
    body_types, transmissions = Scraping.get_body_types_trans(make, model)
    return render_template('pulls-body_types.html',
                           make=make, model=model,
                           body_types=body_types,
                           transmissions=transmissions,
                           pull_id=pull_id)


@app.route('/pulls/final/<string:make>/<string:model>/<string:pull_id>')
def pull_final(make, model, pull_id):
    body_types = request.args.get('body_types')
    if body_types == "Select":
        body_types = ""
    transmissions = request.args.getlist('transmission')
    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')
    min_kms = request.args.get('min_kms')
    max_kms = request.args.get('max_kms')
    min_year = request.args.get('min_year')
    max_year = request.args.get('max_year')
    mandatory_keywords = request.args.get('mandatory_keywords')
    mandatory_keywords = mandatory_keywords.split()
    optional_keywords = request.args.get('optional_keywords')
    optional_keywords = optional_keywords.split()
    user = User.get_by_email(session['email'])
    pull_id = None if pull_id == 'None' else pull_id
    pull = Pull(_id=pull_id,
                author_id=user._id,
                type="autos",
                make=make,
                model=model,
                body_types=body_types,
                transmissions=transmissions,
                min_price=min_price,
                max_price=max_price,
                min_kms=min_kms,
                max_kms=max_kms,
                min_year=min_year,
                max_year=max_year,
                mandatory_keywords=mandatory_keywords,
                optional_keywords=optional_keywords)
    if pull_id is None:
        pull.generate_kijiji_url()
        pull.generate_autotrader_url()
        pull.save_to_mongo()
        pull.body_types
    else:
        pull.generate_kijiji_url()
        pull.generate_autotrader_url()
        old_pull = Pull.from_mongo(pull_id)
        old_pull.update_pull(pull.json())
        pull = old_pull
    pull.generate_kijiji_posts_data(new_or_update='new')
    pull.generate_autotrader_posts_data(new_or_update='new')
    return make_response(start_pull())

@app.route('/posts/<string:pull_id>')
def load_posts(pull_id):
    pull = Pull.from_mongo(pull_id)
    posts = Post.from_mongo(pull_id)
    return render_template('posts.html', pull=pull, posts=posts)

@app.route('/flags/<string:variable>/<string:flag>/<string:post_id>/<string:template>')
def change_flags(variable, flag, post_id, template):
    post = Post.from_mongo_post_id(post_id)
    if flag == 'True':
        flag = True
    else:
        flag = False
    if variable == 'star':
        post.update_post(
            {"_id": post._id, "location": post.location, "kms": post.kms, "image": post.image, "title": post.title,
             "date_posted": post.date_posted, "seller": post.seller, "prices": post.prices, "transmission": post.transmission,
             "description": post.description, "url": post.url, "pull_id": post.pull_id, "hide": post.hide, "star": flag, "type": post.type})
    else:
        post.update_post(
            {"_id": post._id, "location": post.location, "kms": post.kms, "image": post.image, "title": post.title,
             "date_posted": post.date_posted, "seller": post.seller, "prices": post.prices, "transmission": post.transmission,
             "description": post.description, "url": post.url, "pull_id": post.pull_id, "hide": flag, "star": post.star, "type": post.type})
    if template == 'starred_posts.html':
        user = User.get_by_email(session['email'])
        pulls = Pull.find_by_author_id(user.id)
        posts = []
        for pull in pulls:
            try:
                posts = posts + Post.get_starred_posts(pull._id)
            except TypeError:
                continue
    else:
        pull = Pull.from_mongo(post.pull_id)
        posts = Post.from_mongo(pull._id)
    if template == 'posts.html':
        return make_response(load_posts(pull._id))
    elif template == 'all_posts.html':
        return make_response(get_all_posts())
    elif template == 'starred_posts.html':
        make_response(starred_posts())
    elif template == 'price_drops.html':
        make_response(price_drops())
    else:
        return render_template(template, pull=pull, posts=posts)


@app.route('/starred')
def starred_posts():
    user = User.get_by_email(session['email'])
    pulls = Pull.find_by_author_id(user.id)
    posts = []
    for pull in pulls:
        try:
            posts = posts + Post.get_starred_posts(pull._id)
        except TypeError:
            continue
    return render_template('starred_posts.html', posts=posts)

@app.route('/price_drops')
def price_drops():
    user = User.get_by_email(session['email'])
    pulls = Pull.find_by_author_id(user.id)
    posts_list = []
    for pull in pulls:
        posts = Post.from_mongo(pull._id)
        for post in posts:
            if len(post.prices) > 1:
                posts_list.append(post)
    return render_template('price_drops.html', posts=posts_list)


@app.route('/all_posts')
def get_all_posts():
    user = User.get_by_email(session['email'])
    pulls = Pull.find_by_author_id(user.id)
    posts = []
    for pull in pulls:
        posts = posts + Post.from_mongo(pull._id)
    return render_template('all_posts.html', posts=posts)

@app.route('/editpull/<string:change>/<string:pull_id>')
def edit_pull(change, pull_id):
    if change == 'delete':
        pull = Pull.from_mongo(pull_id)
        pull.delete_pull()
    return make_response(start_pull())

@app.route('/refresh_posts')
def refresh():
    posts = request.args.get('post')
    pull = request.args.get('pull')
    template = 'pulls.html'
    user = User.get_by_email(session['email'])
    pulls = Pull.find_by_author_id(user.id)
    ScheduledTasks.update_posts(pulls)
    return render_template(template, posts=posts, pull=pull, pulls=pulls)

if __name__ == '__main__':
    app.run()