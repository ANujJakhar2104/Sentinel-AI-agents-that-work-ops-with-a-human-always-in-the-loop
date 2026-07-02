import { useState } from 'react'
import './App.css'

function App() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I am Sentinel AI. How can I help you today?' }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  // API URL from .env, fallback to localhost:8000
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  // YEH NAYA FUNCTION HAI: Jo har 2 second mein status check karega
  const pollTaskStatus = async (taskId) => {
    try {
      const response = await fetch(`${API_URL}/api/tasks/${taskId}`);
      const data = await response.json();

      // 1. Task Completed Successfully
      if (data.status === "completed" || data.current_state === "executed") {
        let finalResult = "✅ Task completed successfully.";
        
        if (data.output && Array.isArray(data.output.results)) {
           if (data.output.results.length === 0) {
              finalResult = "You're welcome! Is there anything else I can help you with?";
           } else {
              finalResult = "✅ Action completed! Your request has been processed and an email has been sent.";
           }
        }
        setMessages(prev => [...prev, { role: 'assistant', content: finalResult }]);
        setIsLoading(false); 
      } 
      // 2. YEH NAYA BLOCK HAI: Task Escalated to Human
      else if (data.status === "escalated" || data.current_state === "escalated") {
        let escalationMsg = "⚠️ This issue has been escalated to a human agent.";
        
        // Backend se reason extract karke dikhao
        if (data.output && data.output.escalation && data.output.escalation.reason) {
          escalationMsg = `⚠️ Escalated to Human Support: ${data.output.escalation.reason}`;
        }
        
        setMessages(prev => [...prev, { role: 'assistant', content: escalationMsg }]);
        setIsLoading(false);
      }
      // 3. Task Failed
      else if (data.status === "failed" || data.status === "error") {
        setMessages(prev => [...prev, { role: 'assistant', content: `❌ Task Failed.` }]);
        setIsLoading(false);
      } 
      // 4. Still processing, keep checking
      else {
        setTimeout(() => pollTaskStatus(taskId), 2000);
      }
    } catch (error) {
      console.error("Polling error:", error);
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim()) return

    const userText = input
    setMessages(prev => [...prev, { role: 'user', content: userText }])
    setInput('')
    setIsLoading(true)

    try {
      // 1. Initial request bhej rahe hain
      const response = await fetch(`${API_URL}/api/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          input: { input_text: userText, priority: 5 } 
        })
      })

      const data = await response.json()
      
      // 2. Agar API ne ID de di, matlab task queue mein chala gaya
      if (data.id) {
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: `⏳ Request received! Checking details... (Task ID: ${data.id.split('-')[0]})` 
        }])
        
        // 3. Polling start kardo (Peeche API se puchte raho)
        pollTaskStatus(data.id);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: JSON.stringify(data) }])
        setIsLoading(false)
      }
    } catch (error) {
      console.error(error)
      setMessages(prev => [...prev, { role: 'assistant', content: 'Error: Cannot connect to Sentinel backend.' }])
      setIsLoading(false)
    }
  }

  return (
    <div className="chat-container">
      <header className="chat-header">
        <h2>🛡️ Sentinel AI</h2>
      </header>
      
      <div className="chat-messages">
        {messages.map((msg, index) => (
          <div key={index} className={`message-row ${msg.role}`}>
            <div className={`message-bubble ${msg.role}`}>
              {msg.content}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message-row assistant">
            <div className="message-bubble assistant loading">
              Sentinel is processing...
            </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="chat-input-form">
        <input 
          type="text" 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. My order 12345 arrived damaged, please refund $49.99"
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading || !input.trim()}>Send</button>
      </form>
    </div>
  )
}

export default App