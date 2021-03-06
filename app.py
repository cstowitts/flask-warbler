import os

from flask import Flask, render_template, request, flash, redirect, session, g, url_for
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError

from forms import UserAddForm, LoginForm, MessageForm, CSRFProtectForm, EditUserForm
from models import db, connect_db, User, Message, Likes, Follows

CURR_USER_KEY = "curr_user"  # this is the key in the session

app = Flask(__name__)

# Get DB_URI from environ variable (useful for production/testing) or,
# if not set there, use development local db.
app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ['DATABASE_URL'].replace("postgres://", "postgresql://"))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True  # originally False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = True
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
toolbar = DebugToolbarExtension(app)

connect_db(app)


##############################################################################
# User signup/login/logout


@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])

    else:
        g.user = None


@app.before_request
def add_crsf_form_to_all_pages():
    """Before every route, add CSRF-only form to global object"""

    g.csrf_form = CSRFProtectForm()


def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id


def do_logout():
    """Logout user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """

    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            db.session.commit()

        except IntegrityError:
            flash("Username already taken", 'danger')
            return render_template('users/signup.html', form=form)

        do_login(user)

        return redirect("/")

    else:
        return render_template('users/signup.html', form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data,
                                 form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)


@app.post('/logout')
def logout():
    """Handle logout of user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    if g.csrf_form.validate_on_submit():
        do_logout()
        flash("You've successfully logged out!")

    return redirect("/")


##############################################################################
# General user routes:

@app.get('/users')
def list_users():
    """Page with listing of users.

    Can take a 'q' param in querystring to search by that username.
    """

    search = request.args.get('q')

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template('users/index.html', users=users)


@app.get('/users/<int:user_id>')
def users_show(user_id):
    """Show user profile."""

    user = User.query.get_or_404(user_id)

    return render_template('users/show.html', user=user)


@app.get('/users/<int:user_id>/following')
def show_following(user_id):
    """Show list of people this user is following."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/following.html', user=user)


@app.get('/users/<int:user_id>/followers')
def users_followers(user_id):
    """Show list of followers of this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/followers.html', user=user)


@app.post('/users/follow/<int:follow_id>')
def add_follow(follow_id):
    """Add a follow for the currently-logged-in user."""

    came_from_url = request.form.get("came-from")

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    if g.csrf_form.validate_on_submit():
        followed_user = User.query.get_or_404(follow_id)
        g.user.following.append(followed_user)
        db.session.commit()
        flash(f"You are now following {followed_user.username}!", "info")

    return redirect(came_from_url)


@app.post('/users/stop-following/<int:follow_id>')
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user."""

    came_from_url = request.form.get("came-from")

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    if g.csrf_form.validate_on_submit():
        followed_user = User.query.get(follow_id)
        g.user.following.remove(followed_user)
        db.session.commit()
        flash(f"You've unfollowed {followed_user.username}.", "warning")

    return redirect(came_from_url)


@app.route('/users/profile', methods=["GET", "POST"])
def edit_profile():
    """Update profile for current user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = EditUserForm(obj=g.user)

    if form.validate_on_submit():
        g.user.email = form.email.data
        g.user.username = form.username.data
        g.user.image_url = (form.image_url.data or
                            "/static/images/default-pic.png")
        g.user.header_image_url = (form.header_image_url.data or
                                   "/static/images/warbler-hero.jpg")
        g.user.bio = form.bio.data
        if User.authenticate(g.user.username, form.password.data):
            db.session.commit()
            flash("Profile successfully updated!", 'success')
            return redirect(f'/users/{g.user.id}')
        else:
            flash("Incorrect password.", 'danger')

    return render_template('users/edit.html', form=form)


@app.get('/users/<int:user_id>/liked_messages')
def display_liked_messages(user_id):
    """Display all messages a user has liked"""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)

    return render_template("users/liked_warbles.html", user=user)


@app.post('/users/delete')
def delete_user():
    """Delete user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    if g.csrf_form.validate_on_submit():
        Message.query.filter_by(user_id=g.user.id).delete()
        Follows.query.filter_by(user_being_followed_id=g.user.id).delete()
        Follows.query.filter_by(user_following_id=g.user.id).delete()
        Likes.query.filter_by(liker_id=g.user.id).delete()
        db.session.delete(g.user)
        db.session.commit()
        flash("User successfully deleted :(", "warning")

    return redirect("/signup")


##############################################################################
# Messages routes:

@app.route('/messages/new', methods=["GET", "POST"])
def messages_add():
    """Add a message:

    Show form if GET. If valid, update message and redirect to user page.
    """

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = MessageForm()

    if form.validate_on_submit():
        msg = Message(text=form.text.data)
        g.user.messages.append(msg)
        db.session.commit()

        return redirect(f"/users/{g.user.id}")

    return render_template('messages/new.html', form=form)


@app.get('/messages/<int:message_id>')
def messages_show(message_id):
    """Show a message."""

    msg = Message.query.get(message_id)
    return render_template('messages/show.html', message=msg)


@app.post('/messages/<int:message_id>/delete')
def messages_destroy(message_id):
    """Delete a message."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    if g.csrf_form.validate_on_submit():
        msg = Message.query.get(message_id)
        db.session.delete(msg)
        db.session.commit()
        flash("Your Warble has been deleted.", "warning")

    return redirect(f"/users/{g.user.id}")


##############################################################################
# Likes for messages

# TODO: make a route for /like
#
# updates the database with new like
# use boolean to figure out if liked already or not
# fills in star if truthy/outline star if falsey
# reloads entire page
# how do we grab the correct message when liked?
# how to know where to redirect to?

@app.post('/like/<int:msg_id>')
def like_message(msg_id):
    """Like a message."""

    came_from_url = request.form.get("came-from")

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    if g.csrf_form.validate_on_submit():
        like = Likes(liker_id=g.user.id, message_id=msg_id)
        db.session.add(like)
        db.session.commit()
        flash("Warble message liked!", "success")
    else:
        flash("Warble message like unsuccessful.", "danger")

    return redirect(came_from_url)

# could consolidate into one toggle status function

@app.post('/unlike/<int:msg_id>')
def unlike_message(msg_id):
    """Unlike a message"""

    came_from_url = request.form.get("came-from")

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    if g.csrf_form.validate_on_submit():
        like = Likes.query.filter_by(message_id=msg_id).filter_by(
            liker_id=g.user.id).one_or_none()

        if like:
            db.session.delete(like)
            db.session.commit()
            flash("You have unliked this post!", "warning")
    else:
        flash("Warble message unlike unsuccessful.", "danger")

    return redirect(came_from_url)


# TODO:
# create the actual star/like icon in html
# logic to toggle icon, check if the message has already been liked or not
# action to update database when message is liked/unliked


##############################################################################
# Homepage and error pages


@app.get('/')
def homepage():
    """Show homepage:

    - anon users: no messages
    - logged in: 100 most recent messages of followed_users
    """

    if g.user:
        ids_for_feed = [g.user.id]

        for person in g.user.following:
            ids_for_feed.append(person.id)
        # breakpoint()
        messages = (Message
                    .query
                    .filter(Message.user_id.in_(ids_for_feed))
                    .order_by(Message.timestamp.desc())
                    .limit(100)
                    .all())

        return render_template('home.html', messages=messages)

    else:
        return render_template('home-anon.html')

# TODO: WHY IN GOD'S NAME DOES EVERY CLICK IN THE MESSAGE BOX GO TO THE SAME PLACE?
# EVEN WITH BUTTON ACTION EXPLICITLY NOT??? SO SIMILAR TO SOLUTION??

##############################################################################
# Turn off all caching in Flask
#   (useful for dev; in production, this kind of stuff is typically
#   handled elsewhere)
#
# https://stackoverflow.com/questions/34066804/disabling-caching-in-flask


@app.after_request
def add_header(response):
    """Add non-caching headers on every request."""

    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
    response.cache_control.no_store = True
    return response
