import { useEffect, useState } from 'react';
import Landing from './pages/Landing';

function App() {
  const [message, setMessage] = useState('Connecting...');

  useEffect(() => {
    fetch('/api/health')
      .then(response => response.json())
      .then(data => setMessage(data.status))
      .catch(() => setMessage('Connection failed'));
  }, []);

  return (
    <Landing />

  );
}

export default App;