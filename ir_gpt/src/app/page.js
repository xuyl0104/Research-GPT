"use client";
import { useState, useEffect } from "react";
import ChatUI from "./chatUI";
import Login from "./components/Login";

export default function Page() {
    const [isLoggedIn, setIsLoggedIn] = useState(false);

    useEffect(() => {
        const token = localStorage.getItem("token");
        setIsLoggedIn(!!token);
    }, []);

    const handleLogin = () => {
        setIsLoggedIn(true);
    };

    const handleLogout = () => {
        localStorage.removeItem("token");
        setIsLoggedIn(false);
    };

    return isLoggedIn ? <ChatUI onLogout={handleLogout} /> : <Login onLogin={handleLogin} />;
}
