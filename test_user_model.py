"""User model tests."""

# run these tests like:
#
#    python -m unittest test_user_model.py


import os
from unittest import TestCase

from models import db, User, Message, Follows

# BEFORE we import our app, let's set an environmental variable
# to use a different database for tests (we need to do this
# before we import our app, since that will have already
# connected to the database

os.environ['DATABASE_URL'] = "postgresql:///warbler_test"

# Now we can import app

from app import app

# Create our tables (we do this here, so we only create the tables
# once for all tests --- in each test, we'll delete the data
# and create fresh new clean test data

db.create_all()


class UserModelTestCase(TestCase):
    """Test views for messages."""

    def setUp(self):
        """Create test client, add sample data."""

        User.query.delete()
        Message.query.delete()
        Follows.query.delete()

        self.client = app.test_client()

        u1 = User(
            email="test1@test.com",
            username="testuser1",
            password="HASHED_PASSWORD1"
        )

        u2 = User(
            email="test2@test.com",
            username="testuser2",
            password="HASHED_PASSWORD2"
        )

        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()

        self.u1_id = u1.id
        self.u2_id = u2.id
        

    def test_user_model(self):
        """Does basic model work?"""

        u = User(
            email="test@test.com",
            username="testuser",
            password="HASHED_PASSWORD"
        )

        db.session.add(u)
        db.session.commit()

        # User should have no messages & no followers
        self.assertEqual(len(u.messages), 0)
        self.assertEqual(len(u.followers), 0)
    
    def test_user_is_following(self):
        """Test if user1 is following user 2"""

        u1 = User.query.get(self.u1_id)
        u2 = User.query.get(self.u2_id)

        follow = Follows(
            user_following_id = u1.id,
            user_being_followed_id = u2.id
        )

        db.session.add(follow)
        db.session.commit()

        # User2 should be in user1's following list
        self.assertIn(u2, u1.following)
        # User 1 should be in user 2's followers list
        self.assertIn(u1, u2.followers)

    def test_user_is_not_following(self):
        """Test if user1 is following user 2"""

        u1 = User.query.get(self.u1_id)
        u2 = User.query.get(self.u2_id)

        # User2 should be in user1's following list
        self.assertNotIn(u2, u1.following)
        # User 1 should be in user 2's followers list
        self.assertNotIn(u1, u2.followers)


    ##############
    #Check if METHODS work, not the database!!!!!!

    def test_user_signup(self):
        """Test if you can make new user"""
        new_user = User.signup(
            username = "lupa",
            email="lupa@dogmail.com",
            password = "i-love-laura",
            image_url = None
        )

        self.assertEqual(new_user.username, "lupa")
        self.assertIsInstance(new_user, User)
