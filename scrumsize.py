from google.appengine.api import users
from google.appengine.ext import db
from datetime import datetime, timedelta
import json
import webapp2

ESTIMATES = [1, 2, 3, 5, 8, 13, 20, 40, 100, '?', 'unvote']
KEEPALIVE_TIMEOUT = 5

class Vote(db.Model):
    game = db.StringProperty(indexed=True)
    user = db.UserProperty(indexed=True)
    turn = db.IntegerProperty(indexed=True)
    vote = db.StringProperty()

    @classmethod
    def read_single(cls, game, user, turn):
        turn = int(turn)
        votes = list(cls.gql("WHERE game = :1 AND user = :2 AND turn = :3", game, user, turn))
        if len(votes) == 0:
            return None
        else:
            return votes[0].vote

    @classmethod
    def read_all(cls, game, turn):
        turn = int(turn)
        votes = list(cls.gql("WHERE game = :1 AND turn = :2", game, turn))
        if len(votes) == 0:
            return []
        else:
            return votes[0].vote

    @classmethod
    def cast(cls, game, user, turn, vote):
        turn = int(turn)
        votes = list(cls.gql("WHERE game = :1 AND user = :2 AND turn = :3", game, user, turn))
        if len(votes) == 0:
            vote = Vote(game=game, user=user, turn=turn, vote=vote)
            vote.save()
        else:
            votes[0].vote = vote
            votes[0].save()

    def __repr__(self):
        return "<vote %s %s t%s %s>" % (self.game, self.user, self.turn, self.vote)


class Player(db.Model):
    """Models a user's attendance in a game"""
    user = db.UserProperty()
    game = db.StringProperty(indexed=True)
    when = db.DateTimeProperty(auto_now=True)

    @classmethod
    def load(cls, user=None, game=None):
        if user is None:
            user = users.get_current_user()
        if user is None:
            return None
        players = list(cls.gql("WHERE user = :1 AND game = :2", user, game))
        if len(players) == 0:
            player =  Player(user=user, game=game)
            player.save()
            return player
        else:
            return players[0]

    @property
    def name(self):
        name = self.user.nickname()
        if '@' in name:
            name = name[0:name.find('@')]
        return name

    def checkin(self):
        self.save()  # just updates timestamp

    @classmethod
    def get_players_in_game(self, game):
        cutoff = datetime.today() - timedelta(seconds=KEEPALIVE_TIMEOUT)
        return list(self.gql("WHERE game = :1 AND when >= :2", game, cutoff))

    def __eq__(self, other):
        return (True
            and isinstance(other, self.__class__)
            and self.game == other.game 
            and self.user == other.user)

    def __repr__(self):
        return "<player %s g:%s>" % (self.name, self.game)


class MainPage(webapp2.RequestHandler):

    def get(self):
        user = users.get_current_user()
        if user is None:
            return self.redirect(users.create_login_url(self.request.uri))

        self.response.headers['Content-Type'] = 'text/html'
        self.response.write("""
            <script src="//ajax.googleapis.com/ajax/libs/jquery/1.10.2/jquery.min.js"></script>
            <script src="/script/scrumsize.js"></script>
            <link rel="stylesheet" href="style/scrumsize.css" type="text/css" />
            """)
        game = self.request.get('game', None)
        if game is not None:
            return self.draw_game(game)
        else:
            self.response.write("""
                <title>Planning Poker: Lobby</title>
                <h1>Planning Poker</h1>
                <form>
                    <input type='text' style="width:200px;" name='game' placeholder='game name (any string)'></input>
                    <input type='submit' value='Join game'></input>
                </form>
                """);

    def draw_game(self, game):
        self.response.write("""
            <script type="text/javascript" src="/script/md5.js"></script>
            <script type="text/javascript" src="/script/game.js"></script>
            """)
        self.response.write("<title>%s</title>" % game)
        self.response.write("""
            <table>
                <thhead>
                    <tr>
                        <td></td><td>Last Vote</td><td>This Vote</td><td>Next Vote</td>
                    </tr>
                </thead>
                <tbody id='votes'>
                </tbody>
            </table>
            """)
        self.response.write("<hr>")
        for estimate in ESTIMATES:
            estr = str(estimate)
            button = "<button class='estimate e%s' value='%s' id='%s'>%s</button>" % (estr, estr, estr, estr)
            self.response.write(button)

class Api(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/json'
        game = self.request.get('g', None)
        player = Player.load(game=game)
        vote = self.request.get('v', None)
        turn = int(self.request.get('t', 0))
        player.checkin()


        if game is None:
            opponents = []
        else:
            opponents = Player.get_players_in_game(game)

        if vote is not None:
            if vote == 'unvote':
                vote = None
            Vote.cast(game, player.user, turn, vote)

        while None not in [Vote.read_single(game, opp.user, turn) for opp in opponents]:
            turn += 1

        response = {'opponents': sorted([o.name for o in opponents])}
        response['last_vote'] = {}
        response['this_vote'] = {}
        response['next_vote'] = {}
        for opp in opponents:
            response['last_vote'][opp.name] = Vote.read_single(game, opp.user, turn - 2)
            response['this_vote'][opp.name] = Vote.read_single(game, opp.user, turn - 1)
            response['next_vote'][opp.name] = Vote.read_single(game, opp.user, turn)
        response['turn'] = turn;
        self.response.write(json.dumps(response));
            


application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/api', Api),
], debug=True)
