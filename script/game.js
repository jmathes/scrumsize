$(document).ready(function() {

    function getJsonFromUrl() {
        var query = location.search.substr(1);
        var data = query.split("&");
        var result = {};
        for(var i=0; i<data.length; i++) {
            var item = data[i].split("=");
            result[item[0]] = item[1];
        }
        return result;
    }

    document.turn = 0;
    document.refresh_rate = 1000;
    document.game = getJsonFromUrl().game;
    var keepalive = function() {
        setTimeout(keepalive, document.refresh_rate);
        $.ajax('/api', {
            data: {
                g: document.game,
                t: document.turn
            },
            success: update_users
        });
    };
    var update_users = function(response) {
        document.refresh_rate = response.refresh_rate;
        if (response.timed_out) {
            // window.location = "/?timed_out=" + document.game;
        }
        table = $("#votes");
        table.empty();
        if(response.turn > document.turn) {
            document.turn = response.turn;
        }
        response.opponents.forEach(function(opp, i, arr) {
            var last_vote = response.last_vote[opp] || "";
            var this_vote = response.this_vote[opp] || "";
            var next_vote = response.next_vote[opp] === null ? "waiting" : "ready";
            table
                .append($('<tr>')
                    .append($('<td class="name">').text(opp).css('color', '#' + md5(opp).substr(4,6)))
                    .append($('<td class="last estimate value e' + last_vote + '">').text(last_vote))
                    .append($('<td class="this estimate value e' + this_vote + '">').text(this_vote))
                    .append($('<td class="next estimate mask e' + next_vote + '">').text(next_vote))
                    );
        });
    };
    $('button.estimate').click(function() {
        $.ajax('/api', {
            data: {
                v: this.value,
                g: document.game,
                t: document.turn
            },
            success: update_users,
        });
    });
    keepalive();
});