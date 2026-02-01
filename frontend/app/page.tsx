'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
    A2UIRenderer,
    Surface,
    createEmptySurface,
    setActionHandler,
    clearActionHandler,
} from '@/components/a2ui';
import { parseAGUIStream } from '@/lib/agui';

// --- Chat Message Type ---
interface Message {
    role: 'user' | 'assistant';
    content: string;
    surface?: Surface;
}

// --- Main Page ---
export default function Home() {
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [currentSurface, setCurrentSurface] = useState<Surface | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, scrollToBottom]);

    // Reusable function to send message and process AG-UI stream
    const sendMessage = useCallback(async (message: string, showUserMessage: boolean = true) => {
        if (isLoading) return;

        if (showUserMessage) {
            const userMessage: Message = { role: 'user', content: message };
            setMessages((prev) => [...prev, userMessage]);
        }
        setIsLoading(true);
        setCurrentSurface(null);

        try {
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
            });

            if (!response.ok) throw new Error('Failed to get response');

            const reader = response.body?.getReader();
            if (!reader) throw new Error('No reader available');

            let finalSurface = createEmptySurface('main');

            // Process AG-UI stream
            for await (const result of parseAGUIStream(reader)) {

                // Update surface on each A2UI message
                if (result.surface.isReady) {
                    finalSurface = result.surface;
                    setCurrentSurface({ ...result.surface });

                    // Update or add assistant message
                    setMessages((prev) => {
                        const lastMsg = prev[prev.length - 1];
                        if (lastMsg?.role === 'assistant') {
                            return [
                                ...prev.slice(0, -1),
                                { ...lastMsg, surface: { ...result.surface } },
                            ];
                        } else {
                            return [
                                ...prev,
                                { role: 'assistant', content: '', surface: { ...result.surface } },
                            ];
                        }
                    });
                }

                // Handle completion
                if (result.status === 'completed') {
                    setCurrentSurface(null);
                }

                // Handle errors
                if (result.status === 'error') {
                    // Error handling is done in catch block
                }
            }

            // Ensure assistant message exists with final surface
            setMessages((prev) => {
                const lastMsg = prev[prev.length - 1];
                if (lastMsg?.role !== 'assistant') {
                    return [...prev, { role: 'assistant', content: '', surface: finalSurface }];
                }
                return prev;
            });
        } catch (error) {
            setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: '연결 오류가 발생했습니다. 다시 시도해주세요.' },
            ]);
        } finally {
            setIsLoading(false);
            setCurrentSurface(null);
        }
    }, [isLoading]);

    // Register action handler for A2UI button clicks
    useEffect(() => {
        const handleAction = async (actionName: string, context: Record<string, any>) => {
            // Convert action to natural language message for AI
            const actionMessage = `[Action: ${actionName}] ${JSON.stringify(context)}`;

            // Send action as message to AI via AG-UI stream
            await sendMessage(actionMessage, false);
        };

        setActionHandler(handleAction);

        return () => {
            clearActionHandler();
        };
    }, [sendMessage]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const message = input;
        setInput('');
        await sendMessage(message, true);
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
            {/* Header */}
            <header className="bg-gradient-to-r from-slate-800 to-slate-900 text-white p-4 shadow-lg">
                <div className="max-w-4xl mx-auto">
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        Michael
                    </h1>
                    <p className="text-slate-400 text-sm mt-1">
                        24/7 Personal AI Assistant
                    </p>
                </div>
            </header>

            {/* Chat Area */}
            <main className="max-w-4xl mx-auto p-4 pb-32">
                <div className="space-y-6">
                    {messages.length === 0 && (
                        <div className="text-center py-16">
                            <div className="text-6xl mb-4">🤖</div>
                            <h2 className="text-2xl font-bold text-gray-800 mb-2">
                                안녕하세요, Michael입니다!
                            </h2>
                            <p className="text-gray-500 mb-6">
                                무엇이든 물어보세요. 기억하고, 도와드릴게요.
                            </p>
                            <div className="flex flex-wrap justify-center gap-2">
                                {['오늘 뭐 해야 하지?', '내 스케줄 알려줘', '내일 9시에 알림 설정해줘', '메모 저장해줘'].map(
                                    (suggestion) => (
                                        <button
                                            key={suggestion}
                                            onClick={() => setInput(suggestion)}
                                            className="px-4 py-2 bg-white border border-gray-200 rounded-full text-sm text-gray-700 hover:border-slate-400 hover:text-slate-600 transition-colors shadow-sm"
                                        >
                                            {suggestion}
                                        </button>
                                    )
                                )}
                            </div>
                        </div>
                    )}

                    {messages.map((msg, idx) => (
                        <div
                            key={idx}
                            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div
                                className={`max-w-[85%] ${
                                    msg.role === 'user'
                                        ? 'bg-gradient-to-r from-slate-700 to-slate-800 text-white rounded-2xl rounded-br-md px-5 py-3 shadow-md'
                                        : 'w-full'
                                }`}
                            >
                                {msg.role === 'user' ? (
                                    <p className="whitespace-pre-wrap">{msg.content}</p>
                                ) : (
                                    <>
                                        {/* A2UI v0.8 Renderer */}
                                        {msg.surface?.isReady ? (
                                            <A2UIRenderer surface={msg.surface} />
                                        ) : (
                                            <div className="bg-white rounded-2xl rounded-bl-md px-5 py-4 shadow-md border border-gray-100">
                                                <p className="whitespace-pre-wrap text-gray-700">
                                                    {msg.content || '생각 중...'}
                                                </p>
                                            </div>
                                        )}
                                    </>
                                )}
                            </div>
                        </div>
                    ))}

                    {isLoading && (
                        <div className="flex justify-start">
                            <div className="bg-white rounded-2xl px-5 py-4 shadow-md border border-gray-100">
                                <div className="flex items-center gap-2">
                                    <div className="flex gap-1">
                                        <span
                                            className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                                            style={{ animationDelay: '0ms' }}
                                        />
                                        <span
                                            className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                                            style={{ animationDelay: '150ms' }}
                                        />
                                        <span
                                            className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                                            style={{ animationDelay: '300ms' }}
                                        />
                                    </div>
                                    <span className="text-gray-500 text-sm">
                                        Michael이 생각하고 있어요...
                                    </span>
                                </div>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </main>

            {/* Input Area */}
            <div className="fixed bottom-0 left-0 right-0 bg-white/80 backdrop-blur-lg border-t border-gray-200 p-4">
                <form onSubmit={handleSubmit} className="max-w-4xl mx-auto flex gap-3">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Michael에게 무엇이든 물어보세요..."
                        className="flex-1 border border-gray-300 rounded-xl px-5 py-3 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:border-transparent shadow-sm"
                        disabled={isLoading}
                    />
                    <button
                        type="submit"
                        disabled={isLoading || !input.trim()}
                        className="bg-gradient-to-r from-slate-700 to-slate-900 text-white px-6 py-3 rounded-xl font-medium hover:from-slate-800 hover:to-black disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg"
                    >
                        {isLoading ? '...' : '전송'}
                    </button>
                </form>
            </div>
        </div>
    );
}
