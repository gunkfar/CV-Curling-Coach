const express = require('express'); // To build an application server or API

const router = express.Router(); // new addition, not from old index.js file
// use router to let us define routes instead of having to put everything in index
const auth = require('../middleware/auth');

router.get('/', (req, res) => {
  res.redirect('/landing');
});

router.get('/landing', (req, res) => {
  res.render('pages/landing', {
    username: req.session.username,
  });
});

router.get('/home', auth, async (req, res) => {
  res.render('pages/home', {
    username: req.session.username,
    last_name: req.session.last_name,
    first_name: req.session.first_name,
  });
});

module.exports = router;