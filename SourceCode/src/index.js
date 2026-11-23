// <!-- Import Dependencies -->
const path = require('path');
const express = require('express');
const app = express();
app.use('/resources', express.static(path.join(__dirname, 'resources')));
const handlebars = require('express-handlebars');
const bodyParser = require('body-parser');
const session = require('express-session'); // To set the session object. To store or access session data, use the `req.session`, which is (generally) serialized as JSON by the store.

const pageRoutes = require('./routes/pageRoutes');
const authRoutes = require('./routes/authRoutes');
const gameRoutes = require('./routes/gameRoutes');

// create `ExpressHandlebars` instance and configure the layouts and partials dir.
const hbs = handlebars.create({
  extname: 'hbs',
  layoutsDir: __dirname + '/views/layouts',
  partialsDir: __dirname + '/views/partials',
  helpers: {
    eq: (a, b) => a === b, 
  }
});

// <!-- App Settings -->
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

app.use('/', pageRoutes);
app.use('/', authRoutes);
app.use('/', gameRoutes);

// <!--Start Server-->
// starting the server and keeping the connection open to listen for more requests
const port = 3000;
module.exports = app.listen(3000);
console.log(`test test testServer is listening on port ${port}`);