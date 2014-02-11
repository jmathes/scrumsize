from google.appengine.api import users
from google.appengine.ext import ndb
from datetime import datetime, timedelta
import json
import webapp2

ESTIMATES = [1, 2, 3, 5, 8, 13, 20, 40, 100, '?', 'unvote']
KEEPALIVE_TIMEOUT = 30
IDLE_TIMEOUT = 1200


class Vote(ndb.Model):
    user = ndb.UserProperty(indexed=True)
    turn = ndb.IntegerProperty(indexed=True)
    vote = ndb.StringProperty()
    when = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def key(cls, game):
        return ndb.Key('Vote', game)

    @classmethod
    def read_single(cls, game, user, turn):
        turn = int(turn)
        votes = list(cls.gql("WHERE user = :1 AND turn = :2 AND ANCESTOR IS :3", user, turn, Vote.key(game)))
        if len(votes) == 0:
            return None
        else:
            return votes[0].vote

    @classmethod
    def read_all(cls, game, turn):
        turn = int(turn)
        votes = list(cls.gql("WHERE turn = :1 AND ANCESTOR IS :2", turn, Vote.key(game)))
        if len(votes) == 0:
            return []
        else:
            return votes[0].vote

    @classmethod
    def cast(cls, game, user, turn, vote):
        turn = int(turn)
        votes = list(cls.gql("WHERE user = :1 AND turn = :2 AND ANCESTOR IS :3", user, turn, Vote.key(game)))
        if len(votes) == 0:
            vote = Vote(user=user, turn=turn, vote=vote, parent=cls.key(game))
            vote.put()
        else:
            votes[0].vote = vote
            votes[0].put()

    def __repr__(self):
        return "<vote %s %s t%s %s>" % (self._entity_key, self.user, self.turn, self.vote)


class Player(ndb.Model):
    """Models a user's attendance in a game"""
    user = ndb.UserProperty()
    when = ndb.DateTimeProperty(auto_now=True)
    idle_since = ndb.DateTimeProperty(auto_now_add=True)

    @classmethod
    def key(cls, game):
        return ndb.Key('Player', game)

    @classmethod
    def load(cls, user=None, game=None):
        if user is None:
            user = users.get_current_user()
        if user is None:
            return None
        players = list(cls.gql("WHERE user = :1 AND ANCESTOR IS :2", user, Player.key(game)))
        if len(players) == 0:
            player =  Player(user=user, parent=cls.key(game))
            player.put()
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
        self.put()  # just updates timestamp

    @classmethod
    def get_players_in_game(self, game):
        cutoff = datetime.today() - timedelta(seconds=KEEPALIVE_TIMEOUT)
        return list(self.gql("WHERE when >= :1 AND ANCESTOR IS :2", cutoff, Player.key(game)))

    def __eq__(self, other):
        return (True
            and isinstance(other, self.__class__)
            and self._entity_key == other._entity_key 
            and self.user == other.user)

    def __repr__(self):
        return "<player %s g:%s>" % (self.name, self._entity_key)


class MainPage(webapp2.RequestHandler):

    def get(self):
        user = users.get_current_user()
        if user is None:
            return self.redirect(users.create_login_url(self.request.uri))

        self.response.headers['Content-Type'] = 'text/html'
        self.response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        self.response.headers['Pragma'] = 'no-cache'
        self.response.headers['Expires'] = '0'
        self.response.write("""
            <script src="//ajax.googleapis.com/ajax/libs/jquery/1.10.2/jquery.min.js"></script>
            <script src="/script/scrumsize.js"></script>
            <link rel="stylesheet" href="style/scrumsize.css" type="text/css" />
            """)
        game = self.request.get('game', None)
        timeout_html = ""
        booted_from = self.request.get('timed_out', None)
        if booted_from is not None:
            timeout_html = "<p>timed out of %s</p><p><a href='/?game=%s'>rejoin %s</a></p>" % (booted_from, booted_from, booted_from)
        if game is not None:
            player = Player.load(user=user, game=game)
            player.idle_since = datetime.today()
            player.put()
            return self.draw_game(game)
        else:
            self.response.write("""
                <title>Planning Poker: Lobby</title>
                <h1>Planning Poker</h1>
                %s
                <form>
                    <input type='text' style="width:200px;" name='game' placeholder='game name (any string)'></input>
                    <input type='submit' value='Join game'></input>
                </form>
                """ % timeout_html);

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
            player.idle_since = datetime.today()
            player.put()

        while None not in [Vote.read_single(game, opp.user, turn) for opp in opponents]:
            turn += 1

        response = {'opponents': sorted([o.name for o in opponents])}
        response['refresh_rate'] = 1000
        response['last_vote'] = {}
        response['this_vote'] = {}
        response['next_vote'] = {}
        for opp in opponents:
            response['last_vote'][opp.name] = Vote.read_single(game, opp.user, turn - 2)
            response['this_vote'][opp.name] = Vote.read_single(game, opp.user, turn - 1)
            response['next_vote'][opp.name] = Vote.read_single(game, opp.user, turn)
        response['turn'] = turn;
        if datetime.today() - player.idle_since > timedelta(seconds=IDLE_TIMEOUT):
            response['timed_out'] = True

        self.response.write(json.dumps(response));
            


application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/api', Api),
], debug=True)
