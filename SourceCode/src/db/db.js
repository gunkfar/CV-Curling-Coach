// contains the PostgreSQL database connection code (all taken from index.js)

const pgp = require('pg-promise')(); // To connect to the Postgres DB from the node server

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

module.exports = db; // not included in original index.js file 