import React, { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'

function App() {
  const [messages, setMessages] = useState([
    { id: 1, text: '¡Hola! Soy tu asistente de compras. ¿En qué puedo ayudarte hoy?', sender: 'bot' }
  ])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!inputValue.trim() || isLoading) return

    const userMessage = { id: Date.now(), text: inputValue, sender: 'user' }
    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    try {
      const res = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: userMessage.text })
      })
      if (!res.ok) throw new Error('Error en el servidor')
      const data = await res.json()
      setMessages(prev => [...prev, { id: Date.now() + 1, text: data.response, sender: 'bot' }])
    } catch (err) {
      console.error(err)
      setMessages(prev => [...prev, { id: Date.now() + 1, text: 'Ocurrió un error. Intenta nuevamente.', sender: 'bot' }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      handleSubmit(e)
    }
  }

  return (
    <div className="app">
      <header className="app-header"><h1>Asistente de Compras</h1></header>

      <div className="chat-container">
        <div className="messages">
          {messages.map(m => (
            <div key={m.id} className={`message ${m.sender}`}>
              <div className="avatar">{m.sender === 'bot' ? 'A' : 'T'}</div>
              <div className="bubble message-content">
                {m.sender === 'bot' ? (
                  <ReactMarkdown>{m.text}</ReactMarkdown>
                ) : (
                  m.text
                )}
              </div>
            </div>
          ))}
          <div ref={endRef} />
          {isLoading && (
            <div className="message bot">
              <div className="avatar">A</div>
              <div className="bubble message-content typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="input-area">
          <textarea
            rows={1}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe tu mensaje aquí... (Shift+Enter para salto de línea)"
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading || !inputValue.trim()}
            aria-label="Enviar">
            {isLoading ? '...' : 'Enviar'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default App
