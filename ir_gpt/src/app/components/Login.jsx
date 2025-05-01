import { useState } from "react";

export default function Login({ onLogin }) {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [isRegistering, setIsRegistering] = useState(false);
    const [error, setError] = useState("");

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");

        const endpoint = isRegistering ? "register" : "login";

        try {
            const res = await fetch(`http://localhost:8000/${endpoint}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || "Login/Register failed");
            }

            if (!isRegistering) {
                // login mode: store token and proceed
                localStorage.setItem("token", data.access_token);
                onLogin();
            } else {
                // register mode: auto switch to login view
                setIsRegistering(false);
                setUsername("");
                setPassword("");
            }
        } catch (err) {
            setError(err.message);
        }
    };

    return (
        <form
            onSubmit={handleSubmit}
            className="max-w-sm mx-auto mt-20 p-6 bg-white rounded shadow"
        >
            <h2 className="text-xl font-semibold mb-4 text-center">
                {isRegistering ? "Register" : "Login"}
            </h2>

            <input
                type="text"
                className="w-full p-2 mb-3 border rounded"
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
            />

            <input
                type="password"
                className="w-full p-2 mb-3 border rounded"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
            />

            <button
                type="submit"
                className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700"
            >
                {isRegistering ? "Create Account" : "Log In"}
            </button>

            {error && <p className="text-red-500 mt-2 text-sm">{error}</p>}

            <p className="text-sm text-center mt-4">
                {isRegistering ? "Already have an account?" : "Don't have an account?"}{" "}
                <button
                    type="button"
                    onClick={() => {
                        setIsRegistering(!isRegistering);
                        setError("");
                    }}
                    className="text-blue-600 hover:underline"
                >
                    {isRegistering ? "Log In" : "Register"}
                </button>
            </p>
        </form>
    );
}
