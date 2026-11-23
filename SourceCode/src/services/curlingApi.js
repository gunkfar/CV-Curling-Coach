const axios = require('axios');

///// Get stored game data /////
const getStoredGame = async (gameId) => {
const response = await axios.get(
      `https://rockcreekcurling.com/api/coach/storage/${gameId}`,
      {
        headers: {
          Authorization: `Bearer ${process.env.API_KEY}`
        }
      }
    );
  return response;
};

const getGamesOnDate = async (selectedDate) => {
    const gamesat6 = await axios.get(
      'https://rockcreekcurling.com/api/draw/leagues-at',
      {
        params: {
          t: `${selectedDate}T18:00:00` // 6:00 pm
        }
      }
    );

  const gamesat815 = await axios.get(
    'https://rockcreekcurling.com/api/draw/leagues-at',
    {
        params: {
        t: `${selectedDate}T20:15:00`// 8:15 pm
        }
    }
    );

  return { gamesat6, gamesat815 };
};

module.exports = { getStoredGame, getGamesOnDate };


