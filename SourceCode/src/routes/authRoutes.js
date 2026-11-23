const express = require('express'); // creates router
const router = express.Router();

const bcrypt = require('bcryptjs'); //  To hash passwords
const db = require('../db/db'); // uses PostgreSQL connection

///// login get and post /////
router.get('/login', (req, res) => {
  res.render('pages/login',
  {
   username: req.session.username,
   last_name: req.session.last_name,
   first_name: req.session.first_name,
  });
});

router.post('/login', async (req, res) => {
  const user1 = {
    uname: 'JaneDoe',
    fname: 'Jane',
    lname: 'Doe',
    pwd: 'test123',
  }

  const user2 = {
    uname: 'JohnDoe',
    fname: 'John',
    lname: 'Doe',
    pwd: 'test456',
  }


  const userarr = [user1, user2];

  for (let i = 0; i < userarr.length; i++) {
    const hash = await bcrypt.hash(userarr[i].pwd, 10);
    const query = `INSERT INTO users (first_name, last_name, username, password) VALUES ($1, $2, $3, $4) ON CONFLICT (username) DO NOTHING;`; 
    await db.none(query, [userarr[i].fname, userarr[i].lname, userarr[i].uname, hash]).then(courses => { 
    })
    .catch(err => {
      res.status(400);
  });
  }

  const username = req.body.username;
  const query = 'SELECT * FROM users WHERE username = $1 LIMIT 1';

  db.one(query, [username])
    .then(async user => {
      if (!user) {
        return res.render('pages/register', {
        });
      }
      const match = await bcrypt.compare(req.body.password, user.password);
      if (!match) {
        return res.render('pages/login', {
          message: 'Incorrect password',
          error: true
        });
      }
      req.session.last_name = user.last_name,
      req.session.first_name = user.first_name,
      req.session.username = user.username;

      user.initials = (user.first_name[0] + user.last_name[0]).toUpperCase();
      req.session.user = user;
      req.session.save();

      res.redirect('/home');
    })
    .catch(err => {
      res.render('pages/register', {
      });
    });
});

///// register get and post /////
router.get('/register', (req, res) => {
  res.render('pages/register');
});

router.post('/register', async (req, res) => {
  try {
    const { first_name, last_name, username, password } = req.body;

    const hash = await bcrypt.hash(password, 10);

    const query = `INSERT INTO users (first_name, last_name, username, password) VALUES ($1, $2, $3, $4) ON CONFLICT (username) DO NOTHING RETURNING user_id, username, first_name, last_name;`;
    const user = await db.oneOrNone(query, [first_name, last_name, username, hash]);

    // username  exists
    if (!user) {
      return res.status(409).render('pages/register', {
        error: 'That username is already taken.'
      });
    }

    // login session
    req.session.user = {
      user_id: user.user_id,
      username: user.username,
      first_name: user.first_name,
      last_name: user.last_name,
      initials: (user.first_name[0] + user.last_name[0]).toUpperCase()
    };

    // wait for the session to save before redirecting
    req.session.save((err) => {
      if (err) {
        console.error(err);
        return res.status(500).send('Unable to start your session.');
      }
      res.redirect('/home');
    });

  } catch (err) {
    console.error(err);
    res.status(500).render('pages/register', {
      error: 'Unable to create your account. Please try again.'
    });
  }
});

///// logout /////
router.get('/logout', async (req, res) => {
  req.session.destroy();
  res.redirect('/landing');
});

module.exports = router;