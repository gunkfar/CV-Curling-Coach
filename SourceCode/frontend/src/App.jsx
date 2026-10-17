import { useEffect, useState } from 'react';

function App() {
  const [message, setMessage] = useState('Connecting...');

  useEffect(() => {
    fetch('/api/health')
      .then(response => response.json())
      .then(data => setMessage(data.status))
      .catch(() => setMessage('Connection failed'));
  }, []);

  return (
    <main>
      <h1>CV Curling Coach</h1>
      <p>{message}</p>
    </main>
  );
}

export default App;