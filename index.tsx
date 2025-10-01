import { useState } from "react";
import { motion } from "framer-motion";
import { Send, Sun, Moon } from "lucide-react";

export default function ChatbotUI() {
  const [messages, setMessages] = useState([
    { sender: "bot", text: "Hey! I’m your AI assistant. What’s up?" },
  ]);
  const [input, setInput] = useState("");
  const [darkMode, setDarkMode] = useState(true);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { sender: "user", text: input };
    setMessages([...messages, userMessage]);
    setInput("");

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input }),
      });
      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: data.reply },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "⚠️ Error talking to server." },
      ]);
    }
  };

  return (
    <div
      className={`min-h-screen flex flex-col p-2 transition-colors duration-300 ${
        darkMode ? "bg-gray-900" : "bg-white"
      }`}
    >
      <div className="flex justify-end p-2">
        <button
          onClick={() => setDarkMode(!darkMode)}
          className={`p-2 rounded-md transition-colors ${
            darkMode
              ? "bg-gray-700 hover:bg-gray-600 text-white"
              : "bg-gray-200 hover:bg-gray-300 text-black"
          }`}
        >
          {darkMode ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>

      <div
        className={`flex-1 overflow-y-auto space-y-3 mb-3 px-2 scrollbar-thin ${
          darkMode ? "scrollbar-thumb-gray-600" : "scrollbar-thumb-gray-300"
        }`}
      >
        {messages.map((msg, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, scale: 0.9, y: 15 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className={`relative px-4 py-2 text-sm max-w-[75%] bubble ${
              msg.sender === "user"
                ? darkMode
                  ? "ml-auto bg-green-600 text-white rounded-2xl rounded-br-none"
                  : "ml-auto bg-green-500 text-white rounded-2xl rounded-br-none"
                : darkMode
                ? "bg-gray-700 text-gray-200 rounded-2xl rounded-bl-none"
                : "bg-gray-100 text-gray-800 rounded-2xl rounded-bl-none"
            }`}
          >
            {msg.text}
          </motion.div>
        ))}
      </div>

      <div className="relative flex items-center px-2 pb-2">
        <input
          placeholder="Type your message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          className={`flex-1 text-sm px-3 py-2 border rounded-full pr-10 ${
            darkMode
              ? "bg-gray-900 border-gray-600 text-white placeholder-gray-400"
              : "bg-white border-gray-300 text-black placeholder-gray-500"
          }`}
        />
        <button
          onClick={sendMessage}
          className={`absolute right-4 p-1 rounded-full transition-colors ${
            darkMode
              ? "text-white hover:text-green-400"
              : "text-black hover:text-green-600"
          }`}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}