const express = require('express');
const router = express.Router();

const auth = require('../middleware/auth');
const { getStoredGame, getGamesOnDate } = require('../services/curlingApi');
const db = require('../db/db');

router.get('/game', auth, async (req, res) => {
  const gameId = req.query.gameId;

  try {
    const response = await getStoredGame(gameId);

    const gameData = response.data;

    //const file = path.join(__dirname, 'exampleGame.json'); //testing
    // const gameData = JSON.parse(fs.readFileSync(file, 'utf8')); //testing
    const gameDataJson = JSON.stringify(gameData).replace(/</g, '\\u003c');
    res.render('pages/game', {
    gameId,
    gameData,
    gameDataJson
    });

  } catch (error) {
    if (error.response?.status === 404) {
      console.log('404 branch hit');
      return res.render('pages/game', {
        gameId,
        gameData: null,
        gameDataJson: 'null'
      }); 
    }

    console.error('Storage API error:', error.message);
    res.status(502).send('Unable to retrieve game data.');
  }
});

router.get('/gamesOnDate', auth, async (req, res) => {
  const selectedDate = req.query.date; // date that is queried from calendar click 

  try {
    const { gamesat6, gamesat815 } = await getGamesOnDate(selectedDate);

    const leagues6 = gamesat6.data.leagues.map(league => ({
      ...league,
      games: league.games.map(game => ({
        ...game,
        game_id: `${selectedDate}-1800-${game.sheet}`
      }))
    }));

    const leagues815 = gamesat815.data.leagues.map(league => ({
      ...league,
      games: league.games.map(game => ({
        ...game,
        game_id: `${selectedDate}-2015-${game.sheet}`
      }))
    }));

    res.render('pages/gamesOnDate', {
      selectedDate,
      leagues6,
      leagues815
    });

  } catch (error) {
    console.error('Error fetching curling games:', error.message);
    res.status(500).send('Error loading games');
  }
});


router.put('/game', auth, async(req, res) => {
  try {
    const gameId = req.query.gameId;
    const userId = req.session.user.user_id;
    const query = `UPDATE users 
                   SET saved_games = array_append(saved_games, $1)
                   WHERE user_id = $2
                   AND NOT ($1::text = ANY(COALESCE(saved_games, '{}')));`; 
    const result = await db.result(query, [gameId, userId]);
    res.json({success: true, alreadySaved: result.rowCount === 0});
  } catch (err) {
    console.error(err);
    res.status(500).json({error: 'Cannot save game. Please try again'});
  }
});


module.exports = router;