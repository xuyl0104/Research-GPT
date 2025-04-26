"use client"
import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";

export default function ChatUI() {
  const [files, setFiles] = useState([]);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sidebarWidth, setSidebarWidth] = useState(256);
  const sidebarRef = useRef();
  const resizerRef = useRef();
  const isDragging = useRef(false);
  const [selectedFileChunks, setSelectedFileChunks] = useState([]);
  const [embeddingStatus, setEmbeddingStatus] = useState(null);
  const scrollTargetRef = useRef(null);
  const [visibleChunks, setVisibleChunks] = useState({});
  const [expanded, setExpanded] = useState(true);
  const [previewedEvidence, setPreviewedEvidence] = useState([]);
  const [loadedFiles, setLoadedFiles] = useState(new Set());
  const [embeddingList, setEmbeddingList] = useState([]);
  const [selectedEmbedding, setSelectedEmbedding] = useState("");
  const [showEmbeddingDropdown, setShowEmbeddingDropdown] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (isDragging.current) {
        const newWidth = e.clientX;
        if (newWidth > 150 && newWidth < 500) {
          setSidebarWidth(newWidth);
        }
      }
    };
    const handleMouseUp = () => {
      isDragging.current = false;
    };
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  useEffect(() => {
    if (scrollTargetRef.current !== null) {
      const el = document.getElementById(scrollTargetRef.current);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add("ring", "ring-blue-400");
        setTimeout(() => {
          el.classList.remove("ring", "ring-blue-400");
        }, 1500);
        scrollTargetRef.current = null;
      }
    }
  }, [selectedFileChunks]);

  const scrollToChunk = async (chunkId, filename) => {
    const el = document.getElementById(chunkId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("ring", "ring-blue-400");
      setTimeout(() => {
        el.classList.remove("ring", "ring-blue-400");
      }, 1500);
    } else if (filename && !loadedFiles.has(filename)) {
      try {
        const res = await fetch(`http://localhost:5000/preview-chunks?filename=${encodeURIComponent(filename)}`);
        const data = await res.json();
        if (data.chunks) {
          setSelectedFileChunks(data.chunks);
          setVisibleChunks(() => {
            const visibility = {};
            data.chunks.forEach((_, i) => {
              visibility[`chunk-${filename}-${i}`] = true;
            });
            return visibility;
          });
          setLoadedFiles((prev) => new Set(prev).add(filename));
          setTimeout(() => {
            const delayedEl = document.getElementById(chunkId);
            if (delayedEl) {
              delayedEl.scrollIntoView({ behavior: "smooth", block: "center" });
              delayedEl.classList.add("ring", "ring-blue-400");
              setTimeout(() => {
                delayedEl.classList.remove("ring", "ring-blue-400");
              }, 1500);
            }
          }, 300);
        }
      } catch (err) {
        console.error("Failed to auto-load file preview for", filename);
      }
    }
  };

  const toggleChunkVisibility = (chunkId) => {
    setVisibleChunks((prev) => ({
      ...prev,
      [chunkId]: !prev[chunkId]
    }));
  };

  const toggleAllChunks = (show) => {
    const visibility = {};
    selectedFileChunks.forEach((_, idx) => {
      visibility[`chunk-${idx}`] = show;
    });
    setVisibleChunks(visibility);
    setExpanded(show);
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { from: "user", content: input }]);
    const currentInput = input;
    setInput("");
    setError(null);
    try {
      const res = await fetch("http://localhost:5000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: currentInput }),
      });
      const data = await res.json();
      if (res.status !== 200) throw new Error(data.error || "Unknown error");
      if (data.answer) {
        setMessages((prev) => [...prev, { from: "bot", content: data.answer }]);
      }
    } catch (err) {
      console.error("Bot error:", err);
      setError(err.message || "Something went wrong");
    }
  };

  const handleFileUpload = (e) => {
    const uploadedFiles = Array.from(e.target.files).map((f) => ({
      name: f.name,
      path: URL.createObjectURL(f),
      blob: f
    }));
    setFiles((prev) => [...prev, ...uploadedFiles]);
  };

  const handleEmbedding = async () => {
    const name = prompt("Enter a name for this new embedding session:");
    if (!name) return;

    const formData = new FormData();
    files.forEach((file) => {
      if (file.blob) {
        formData.append("files", file.blob, file.name);
      }
    });

    setEmbeddingStatus("Uploading and processing...");
    try {
      const res = await fetch(`http://localhost:5000/embed-files?append=true&name=${encodeURIComponent(name)}`, {
        method: "POST",
        body: formData
      });
      const result = await res.json();
      if (res.status !== 200) throw new Error(result.error || "Unknown error");
      setEmbeddingStatus(result.message || "Embedding complete");
      setSelectedEmbedding(name);
    } catch (err) {
      console.error("Error during embedding:", err);
      setEmbeddingStatus("Error during embedding");
    }
    setTimeout(() => {
      setEmbeddingStatus(null);
    }, 4000);
  };


  const fetchEmbeddingList = async () => {
    try {
      const res = await fetch("http://localhost:5000/list-embeddings");
      const data = await res.json();
      if (res.status !== 200) throw new Error(data.error || "Unknown error");
      setEmbeddingList(data.embeddings || []);
    } catch (err) {
      console.error("Failed to fetch embedding list:", err);
      setError("Could not fetch embedding list.");
    }
  };

  const handleSelectEmbedding = async (name) => {
    try {
      const res = await fetch(`http://localhost:5000/load-embedding?name=${encodeURIComponent(name)}`);
      const data = await res.json();
      if (res.status !== 200) throw new Error(data.error || "Unknown error");
      const savedFiles = data.files.map(name => ({ name, path: "", blob: null }));
      setFiles(savedFiles);
      setSelectedEmbedding(name);
      setShowEmbeddingDropdown(false);
    } catch (err) {
      console.error("Failed to load embedding:", err);
      setError("Could not load selected embedding.");
    }
  };

  const handleLoadSavedEmbedding = async () => {
    await fetchEmbeddingList();
    setShowEmbeddingDropdown(true);
  };

  const handleUnloadEmbedding = () => {
    setFiles([]);
    setMessages([]);
    setSelectedFileChunks([]);
    setVisibleChunks({});
    setLoadedFiles(new Set());
    setSelectedEmbedding("");
    setEmbeddingStatus("Embedding unloaded");
    setTimeout(() => setEmbeddingStatus(null), 4000);
  };

  const handleDeleteEmbedding = async () => {
    if (!selectedEmbedding) {
      alert("No embedding loaded.");
      return;
    }
    try {
      const res = await fetch(`http://localhost:5000/delete-embedding?name=${encodeURIComponent(selectedEmbedding)}`, { method: "POST" });
      const data = await res.json();
      if (res.status !== 200) throw new Error(data.error || "Unknown error");
      setFiles([]);
      setMessages([]);
      setSelectedFileChunks([]);
      setVisibleChunks({});
      setLoadedFiles(new Set());
      setSelectedEmbedding("");
      setEmbeddingStatus("Embedding deleted");
      setTimeout(() => setEmbeddingStatus(null), 4000);
    } catch (err) {
      console.error("Delete embedding failed:", err);
      setError("Failed to delete embedding.");
    }
  };


  const getFileIcon = (filename) => {
    const ext = filename.split('.').pop().toLowerCase();
    switch (ext) {
      case 'pdf': return '📄';
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif': return '🖼️';
      case 'doc':
      case 'docx': return '📝';
      case 'xls':
      case 'xlsx': return '📊';
      case 'zip':
      case 'rar': return '🗜️';
      default: return '📁';
    }
  };

  const handlePreviewChunks = (file) => {
    fetch(`http://localhost:5000/preview-chunks?filename=${encodeURIComponent(file.name)}`)
      .then(res => res.json())
      .then(data => {
        setSelectedFileChunks(data.chunks || []);
        const visibility = {};
        (data.chunks || []).forEach((_, idx) => {
          visibility[`chunk-${file.name}-${idx}`] = true;
        });
        setVisibleChunks(visibility);
        setLoadedFiles((prev) => new Set(prev).add(file.name));
      })
      .catch(() => setSelectedFileChunks(["Failed to load preview"]));
  };

  return (
    <div className="h-screen flex flex-col bg-white text-gray-900">
      <div className="flex flex-1 overflow-hidden">
        {/* sidebar */}
        <aside
          ref={sidebarRef}
          style={{ width: `${sidebarWidth}px` }}
          className="bg-gray-100 border-r p-4 hidden md:flex flex-col relative"
        >
          <h2 className="text-lg font-semibold mb-4">Uploaded Files</h2>

          {/* sidebar-buttons */}
          <div className="space-y-2 mb-4">
            <label className="w-full bg-blue-500 text-white py-2 rounded mb-2 text-center block cursor-pointer">
              Upload Files
              <input type="file" multiple onChange={handleFileUpload} className="hidden" />
            </label>
            <button
              onClick={handleEmbedding}
              className="w-full bg-green-500 hover:bg-green-600 text-white py-2 rounded mb-4"
            >
              Embedding
            </button>

            <button
              onClick={handleLoadSavedEmbedding}
              className="w-full bg-purple-500 hover:bg-purple-600 text-white py-2 rounded mb-4"
            >
              Load Saved Embedding
            </button>

            {showEmbeddingDropdown && (
              <div className="mb-4">
                <select
                  className="w-full border rounded p-2"
                  onChange={(e) => handleSelectEmbedding(e.target.value)}
                  defaultValue=""
                >
                  <option value="" disabled>Select embedding...</option>
                  {embeddingList.map((name) => (
                    <option key={name} value={name}>{name}</option>
                  ))}
                </select>
              </div>
            )}


            <button
              onClick={handleUnloadEmbedding}
              className="w-full bg-yellow-500 hover:bg-yellow-600 text-white py-2 rounded mb-4"
            >
              Unload Embedding
            </button>

            <button
              onClick={handleDeleteEmbedding}
              className="w-full bg-red-500 hover:bg-red-600 text-white py-2 rounded mb-4"
            >
              Delete Embedding
            </button>

            {embeddingStatus && <p className="text-xs text-center text-gray-600 italic mb-4">{embeddingStatus}</p>}

          </div>

          {/* sidebar-Scrollable File List */}

          <div className="flex-1 overflow-y-auto">
            <ul className="space-y-2 text-sm text-gray-700">
              {files.map((file, idx) => (
                <li key={idx} className="truncate">
                  <button
                    onClick={() => handlePreviewChunks(file)}
                    className="flex items-center gap-2 hover:underline truncate w-full text-left"
                    title={file.name}
                  >
                    <span className="shrink-0">{getFileIcon(file.name)}</span>
                    <span className="truncate block w-full">{file.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* sidebar-resizer */}
          <div
            ref={resizerRef}
            onMouseDown={() => (isDragging.current = true)}
            className="absolute top-0 right-0 w-2 h-full cursor-col-resize bg-transparent hover:bg-gray-300"
          ></div>
        </aside>

        {/* header line - ChatBot */}
        <div className="flex-1 flex flex-col">
          <header className="p-4 border-b flex items-center justify-between">
            <h1 className="text-xl font-bold">ChatBot</h1>
            <button className="md:hidden bg-gray-200 px-2 py-1 rounded">☰</button>
          </header>

          {/* messages display */}
          <main className="flex-1 overflow-y-auto p-4 space-y-4" id="chat">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex flex-col gap-1 ${msg.from === "user" ? "items-end" : "items-start"}`}
              >
                {msg.from === "bot" && (
                  <img
                    src={`https://api.dicebear.com/7.x/personas/svg?seed=${msg.from}`}
                    className="w-8 h-8 rounded-full"
                    alt={msg.from}
                  />
                )}
                <div
                  className={`${msg.from === "user"
                    ? "bg-blue-100 text-right w-1/2"
                    : "bg-gray-200 w-[85%]"
                    } p-3 rounded-xl whitespace-pre-wrap max-w-full break-words`}
                >
                  <ReactMarkdown
                    components={{
                      code({ node, inline, className, children, ...props }) {
                        return inline
                          ? <code className="bg-gray-100 rounded px-1">{children}</code>
                          : <pre className="whitespace-pre-wrap break-words bg-gray-100 rounded p-2 overflow-x-auto">{children}</pre>;
                      },
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>
                {msg.evidence && msg.evidence.length > 0 && (
                  <ul className="mt-1 text-sm text-blue-600">
                    {msg.evidence.map((ev, i) => (
                      <li key={i}>
                        <button
                          onClick={() => scrollToChunk(`chunk-${ev.filename}-${ev.chunk_index}`, ev.filename)}
                          className="hover:underline"
                          title={ev.text}
                        >
                          🔍 {ev.filename}, Chunk {ev.chunk_index + 1}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            {error && <div className="text-red-600 text-sm max-w-full break-words">⚠ {error}</div>}

            {selectedFileChunks.map((chunk, idx) => {
              const fileName = files[0]?.name || "file";
              const chunkId = `chunk-${fileName}-${idx}`;
              return (
                <li
                  id={chunkId}
                  key={chunkId}
                  onClick={() => toggleChunkVisibility(chunkId)}
                  className={`cursor-pointer p-2 bg-white rounded border shadow text-gray-800 transition-all duration-300 ${visibleChunks[chunkId] === false ? 'hidden' : ''}`}
                >
                  {chunk}
                </li>
              );
            })}

            <div className="flex items-start gap-3 animate-pulse">
              <img
                src="https://api.dicebear.com/7.x/personas/svg?seed=bot"
                className="w-8 h-8 rounded-full"
                alt="Bot"
              />
              <div className="flex space-x-1 bg-gray-200 p-3 rounded-xl">
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" />
              </div>
            </div>
          </main>

          {/* user input */}
          <form onSubmit={handleSend} className="p-4 border-t flex items-center gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.ctrlKey && e.key === "Enter") {
                  e.preventDefault(); // prevent newline
                  handleSend(e);
                }
              }}
              className="flex-1 resize-none border rounded-lg p-2 h-24 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Type a message..."
            ></textarea>
            <button
              type="submit"
              className="bg-blue-500 text-white px-4 py-2 rounded-lg h-12"
            >
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
