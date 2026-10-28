// <!-- Section 1 : Import Dependencies -->
const path = require('path');
const express = require('express'); // To build an application server or API
const app = express();
app.use('/resources', express.static(path.join(__dirname, 'resources')));
const handlebars = require('express-handlebars');
const Handlebars = require('handlebars');
const pgp = require('pg-promise')(); // To connect to the Postgres DB from the node server
const bodyParser = require('body-parser');
const session = require('express-session'); // To set the session object. To store or access session data, use the `req.session`, which is (generally) serialized as JSON by the store.
const bcrypt = require('bcryptjs'); //  To hash passwords
const axios = require('axios');

// <!-- Section 2 : Connect to DB -->

// create `ExpressHandlebars` instance and configure the layouts and partials dir.
const hbs = handlebars.create({
  extname: 'hbs',
  layoutsDir: __dirname + '/views/layouts',
  partialsDir: __dirname + '/views/partials',
  helpers: {
    eq: (a, b) => a === b, 
  }
});

// database configuration
const dbConfig = {
  host: process.env.POSTGRES_HOST, // the database server
  //host: 'db', // the database server
  
  port: process.env.POSTGRES_PORT, // the database port
  database: process.env.POSTGRES_DB, // the database name
  user: process.env.POSTGRES_USER, // the user account to connect with
  password: process.env.POSTGRES_PASSWORD, // the password of the user account
};

const db = pgp(dbConfig);

// test your database
db.connect()
  .then(obj => {
    console.log('Database connection successful'); // you can view this message in the docker compose logs
    obj.done(); // success, release the connection;
  })
  .catch(error => {
    console.log('ERROR:', error.message || error);
  });

// <!-- Section 3 : App Settings -->
app.engine('hbs', hbs.engine);
app.set('view engine', 'hbs');
app.set('views', path.join(__dirname, 'views'));
app.use(bodyParser.json()); // specify the usage of JSON for parsing request body.

// initialize session variables
app.use(
  session({
    secret: process.env.SESSION_SECRET,
    saveUninitialized: false,
    resave: false,
    cookie: { maxAge: 86400000 }, // Cookie expires in 1 day
  })
);

app.use((req, res, next) => {
  res.locals.user = req.session.user || null;
  next();
});

app.use(
  bodyParser.urlencoded({
    extended: true,
  })
);

// <!-- Section 4 : API Routes -->

///// testing ////

app.get('/', (req, res) => {
    res.redirect('/landing');
});

///// landing page //////
app.get('/landing', (req, res) => {
  res.render('pages/landing', {
    username: req.session.username,
  }); 
});


// Games on selected date
app.get('/gamesOnDate', (req, res) => {
  res.render('pages/gamesOnDate');
});

///// login get and post /////
app.get('/login', (req, res) => {
  res.render('pages/login',
  {
   username: req.session.username,
   last_name: req.session.last_name,
   first_name: req.session.first_name,
  });
});

app.post('/login', async (req, res) => {
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
app.get('/register', (req, res) => {
  res.render('pages/register');
});

app.post('/register', async (req, res) => {
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

///// Authentication Middleware /////
const auth = (req, res, next) => {
  if (!req.session.user) {
    // Default to login page.
    return res.redirect('/login');
  }
  next();
};

// Authentication Required
app.use(auth);

///// home /////
app.get('/home', async(req, res) => {

  res.render('pages/home', {
    username: req.session.username,
    last_name: req.session.last_name,
    first_name: req.session.first_name,
  });
});




///// logout /////
app.get('/logout', async (req, res) => {
  req.session.destroy();
  res.render('pages/logout');
});

// Authentication Required
app.use(auth);

// *****************************************************
// <!-- Section 5 : Start Server-->
// *****************************************************
// starting the server and keeping the connection open to listen for more requests
const port = 3000;
module.exports = app.listen(3000);
console.log(`test test testServer is listening on port ${port}`);