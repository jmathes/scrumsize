$(document).ready(function() {
    console.log(1);

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
    document.game = getJsonFromUrl().game;
    var keepalive = function() {
        $.ajax('/api', {
            data: {
                g: document.game,
                t: document.turn
            },
            success: update_users
        });
        setTimeout(keepalive, 1000);
    };
    var update_users = function(response) {
        table = $("#votes");
        table.empty();
        // console.log(response);
        if(response.turn > document.turn) {
            document.turn = response.turn;
        }
        response.opponents.forEach(function(opp, i, arr) {
            var last_vote = response.last_vote[opp] || "";
            var this_vote = response.this_vote[opp] || "";
            var next_vote = response.next_vote[opp] === null ? "waiting" : "ready";
            table
                .append($('<tr>')
                    .append($('<td>').text(opp))
                    .append($('<td class="last value ' + last_vote + '">').text(last_vote))
                    .append($('<td class="this value ' + this_vote + '">').text(this_vote))
                    .append($('<td class="next value ' + next_vote + '">').text(next_vote))
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