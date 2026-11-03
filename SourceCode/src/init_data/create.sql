CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY, 
    username VARCHAR(50) UNIQUE, 
    first_name VARCHAR(50),
    last_name VARCHAR(50),
<<<<<<< Updated upstream
    password CHAR(60) NOT NULL
=======
    password CHAR(60) NOT NULL 
>>>>>>> Stashed changes
);
