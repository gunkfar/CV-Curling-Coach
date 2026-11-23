const express = require('express');
const router = express.Router();

const auth = require('../middleware/auth');
const { getStoredGame, getGamesOnDate } = require('../services/curlingApi');

router.get('/game', auth, async (req, res) => {
  const gameId = req.query.gameId;

  try {
    const response = await getStoredGame(gameId);

    const gameData = response.data;

    res.render('pages/game', {
      gameId,
      gameData
    });

  } catch (error) {
    if (error.response?.status === 404) {
      // Game has not been processed yet
      return res.render('pages/game', {
        gameId,
        gameData: null
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

module.exports = router;