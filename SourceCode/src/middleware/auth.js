// contains the authentication middleware code (user log in and access checks)

const auth = (req, res, next) => {
  if (!req.session.user) {
    // Default to login page.
    return res.redirect('/login');
  }
  next();
}; // checks to make sure a user is logged in before allowing them to access protected pages

module.exports = auth; // not included in original index.js file 