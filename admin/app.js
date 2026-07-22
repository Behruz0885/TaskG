const { useState, useEffect } = React;

// Navigation Sidebar Component
function Sidebar({ currentTab, setCurrentTab }) {
    return (
        <div className="sidebar">
            <div className="sidebar-brand">
                <i className="fa-solid fa-robot"></i>
                <span>TaskGram AI Admin</span>
            </div>
            <ul className="sidebar-menu">
                <li 
                    className={`menu-item ${currentTab === 'dashboard' ? 'active' : ''}`}
                    onClick={() => setCurrentTab('dashboard')}
                >
                    <i className="fa-solid fa-chart-line"></i>
                    <span>Boshqaruv paneli</span>
                </li>
                <li 
                    className={`menu-item ${currentTab === 'users' ? 'active' : ''}`}
                    onClick={() => setCurrentTab('users')}
                >
                    <i className="fa-solid fa-users"></i>
                    <span>Foydalanuvchilar</span>
                </li>
                <li 
                    className={`menu-item ${currentTab === 'logs' ? 'active' : ''}`}
                    onClick={() => setCurrentTab('logs')}
                >
                    <i className="fa-solid fa-list-check"></i>
                    <span>Buyruqlar tarixi</span>
                </li>
                <li 
                    className={`menu-item ${currentTab === 'broadcast' ? 'active' : ''}`}
                    onClick={() => setCurrentTab('broadcast')}
                >
                    <i className="fa-solid fa-paper-plane"></i>
                    <span>Xabar yuborish</span>
                </li>
            </ul>
        </div>
    );
}

// Header Component
function Header({ title, subtitle, lastUpdated }) {
    return (
        <div className="header">
            <div className="header-title">
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </div>
            <div className="system-status">
                <div className="status-dot"></div>
                <span>Tizim holati: Faol {lastUpdated && <span style={{ opacity: 0.6, marginLeft: '6px', fontSize: '12px' }}>({lastUpdated})</span>}</span>
            </div>
        </div>
    );
}

// Stats Dashboard Component
function DashboardView({ stats, loading, refreshData, setCurrentTab, lastUpdated }) {
    return (
        <div>
            <Header title="Boshqaruv paneli" subtitle="Tizim faoliyati haqida umumiy hisobotlar va holat" lastUpdated={lastUpdated} />
            
            <div className="stats-grid">
                <div className="stat-card" onClick={() => setCurrentTab('users')} style={{ cursor: 'pointer' }}>
                    <div className="stat-info">
                        <h3>Faol hisoblar</h3>
                        <div className="value">{loading ? '...' : stats.active_users}</div>
                    </div>
                    <div className="stat-icon users">
                        <i className="fa-solid fa-users"></i>
                    </div>
                </div>

                <div className="stat-card" onClick={() => setCurrentTab('logs')} style={{ cursor: 'pointer' }}>
                    <div className="stat-info">
                        <h3>Bajarilgan buyruqlar</h3>
                        <div className="value">{loading ? '...' : stats.total_commands}</div>
                    </div>
                    <div className="stat-icon commands">
                        <i className="fa-solid fa-bolt"></i>
                    </div>
                </div>

                <div className="stat-card" onClick={refreshData} style={{ cursor: 'pointer' }} title="Ma'lumotlarni yangilash uchun bosing">
                    <div className="stat-info">
                        <h3>Bot holati</h3>
                        <div className="value">ONLINE</div>
                    </div>
                    <div className="stat-icon status">
                        <i className="fa-solid fa-server"></i>
                    </div>
                </div>
            </div>

            <div className="section-card">
                <div className="section-header">
                    <h2>Bot ma'lumotlari</h2>
                    <button className="refresh-btn" onClick={refreshData}>
                        <i className={`fa-solid fa-arrows-rotate ${loading ? 'loading-spin' : ''}`}></i>
                        Yangilash
                    </button>
                </div>
                
                <div style={{ lineHeight: '1.8', color: 'var(--text-secondary)', fontSize: '15px' }}>
                    <p style={{ marginBottom: '12px' }}>💡 <b>Qo'llanma:</b> Ushbu admin panel orqali bot foydalanuvchilarini, ular yuklagan Telegram sessiyalari va AI orqali yuborilgan buyruqlarini live kuzatishingiz hamda boshqarishingiz mumkin.</p>
                    <p>🤖 Tizim Telegram <b>aiogram 3.x</b> va <b>Telethon</b> asinxron kutubxonalari hamda <b>GLM-5 LLM</b> modeli asosida muvaffaqiyatli ishlamoqda.</p>
                </div>
            </div>
        </div>
    );
}

// Users Management Component
function UsersView({ users, loading, refreshData, onToggleBlock, onDeleteUser, lastUpdated }) {
    return (
        <div>
            <Header title="Foydalanuvchilar" subtitle="Botga o'z Telegram akkauntini ulagan barcha foydalanuvchilar ro'yxati" lastUpdated={lastUpdated} />
            
            <div className="section-card">
                <div className="section-header">
                    <h2>Ulangan hisoblar ro'yxati ({users.length} ta)</h2>
                    <button className="refresh-btn" onClick={refreshData}>
                        <i className={`fa-solid fa-arrows-rotate ${loading ? 'loading-spin' : ''}`}></i>
                        Yangilash
                    </button>
                </div>

                <div className="table-responsive">
                    {users.length === 0 ? (
                        <p style={{ textAlign: 'center', padding: '24px', color: 'var(--text-secondary)' }}>Foydalanuvchilar topilmadi</p>
                    ) : (
                        <table>
                            <thead>
                                <tr>
                                    <th>Foydalanuvchi</th>
                                    <th>Telefon</th>
                                    <th>Til</th>
                                    <th>Sessiya ID</th>
                                    <th>Holat</th>
                                    <th>Ulangan sana</th>
                                    <th>Amallar</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map((u) => (
                                    <tr key={u.user_id}>
                                        <td>
                                            <div style={{ display: 'flex', flexDirection: 'column' }}>
                                                <span style={{ fontWeight: '500', color: 'var(--text-primary)' }}>{u.name || "Noma'lum"}</span>
                                                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                                                    {u.username ? `@${u.username}` : `ID: ${u.user_id}`}
                                                </span>
                                            </div>
                                        </td>
                                        <td style={{ color: 'var(--text-secondary)' }}>{u.phone || "Kiritilmagan"}</td>
                                        <td>
                                            <span style={{ 
                                                textTransform: 'uppercase', 
                                                fontSize: '12px', 
                                                fontWeight: '600', 
                                                color: 'var(--accent-color)',
                                                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                                padding: '2px 6px',
                                                borderRadius: '4px'
                                            }}>
                                                {u.language}
                                            </span>
                                        </td>
                                        <td style={{ fontWeight: '600', color: 'var(--text-primary)' }}>#{u.current_session_id}</td>
                                        <td>
                                            {u.is_blocked ? (
                                                <span className="badge disconnected" style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.3)' }}>
                                                    Bloklangan
                                                </span>
                                            ) : (
                                                <span className={`badge ${u.is_online ? 'connected' : 'disconnected'}`}>
                                                    {u.is_online ? 'Online' : 'Online emas'}
                                                </span>
                                            )}
                                        </td>
                                        <td style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>{u.created_at}</td>
                                        <td>
                                            <div className="btn-action-group">
                                                <button 
                                                    className={`btn-action ${u.is_blocked ? 'btn-success-hover' : 'btn-danger-hover'}`}
                                                    style={{ 
                                                        borderColor: u.is_blocked ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)', 
                                                        color: u.is_blocked ? '#10b981' : '#ef4444' 
                                                    }}
                                                    onClick={() => onToggleBlock(u.user_id, !u.is_blocked)}
                                                >
                                                    <i className={`fa-solid ${u.is_blocked ? 'fa-lock-open' : 'fa-ban'}`} style={{ marginRight: '4px' }}></i>
                                                    {u.is_blocked ? 'Blokdan chiqarish' : 'Bloklash'}
                                                </button>
                                                <button 
                                                    className="btn-action btn-danger-hover"
                                                    style={{ 
                                                        borderColor: 'rgba(239, 68, 68, 0.4)', 
                                                        color: '#ef4444',
                                                        marginLeft: '8px'
                                                    }}
                                                    onClick={() => onDeleteUser(u.user_id)}
                                                >
                                                    <i className="fa-solid fa-trash-can" style={{ marginRight: '4px' }}></i>
                                                    O'chirish
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        </div>
    );
}

// Execution Logs Component
function LogsView({ logs, loading, refreshData, onViewChat, lastUpdated }) {
    return (
        <div>
            <Header title="Buyruqlar tarixi" subtitle="Foydalanuvchilar tomonidan yuborilgan buyruqlar va AI bajarilish loglari" lastUpdated={lastUpdated} />
            
            <div className="section-card">
                <div className="section-header">
                    <h2>Oxirgi amallar va loglar</h2>
                    <button className="refresh-btn" onClick={refreshData}>
                        <i className={`fa-solid fa-arrows-rotate ${loading ? 'loading-spin' : ''}`}></i>
                        Yangilash
                    </button>
                </div>

                        <div className="table-responsive">
                            {logs.length === 0 ? (
                                <p style={{ textAlign: 'center', padding: '24px', color: 'var(--text-secondary)' }}>Loglar topilmadi</p>
                            ) : (
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Username</th>
                                            <th>Amallar</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {logs.map(log => (
                                            <tr key={log.id}>
                                                <td>
                                                    <div style={{ fontWeight: '600', color: 'var(--text-primary)' }}>
                                                        {log.username ? `@${log.username}` : (log.name || `Foydalanuvchi #${log.user_id}`)}
                                                    </div>
                                                    {log.phone && log.phone !== '—' && (
                                                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                                                            <i className="fa-solid fa-phone" style={{ fontSize: '9px', marginRight: '4px' }}></i>
                                                            {log.phone}
                                                        </div>
                                                    )}
                                                </td>
                                                <td>
                                                    <button 
                                                        className="btn-action"
                                                        style={{ borderColor: 'var(--accent-glow)', color: 'var(--accent)' }}
                                                        onClick={() => onViewChat(log.user_id, log.name || `@${log.username}` || log.user_id)}
                                                    >
                                                        <i className="fa-solid fa-comments" style={{ marginRight: '4px' }}></i>
                                                        💬 Suhbat
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
            </div>
        </div>
    );
}


// Broadcast / Send Message Component
function BroadcastView() {
    const [message, setMessage] = useState('');
    const [sending, setSending] = useState(false);
    const [status, setStatus] = useState(null);

    const handleSend = async (e) => {
        e.preventDefault();
        if (!message.trim()) {
            alert("Xabar matnini kiriting!");
            return;
        }
        if (!confirm("Haqiqatan ham barcha foydalanuvchilarga ushbu xabarni yubormoqchimisiz?")) {
            return;
        }
        setSending(true);
        setStatus({ type: 'info', text: 'Xabar yuborilmoqda...' });
        try {
            const res = await fetch('/api/broadcast', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message })
            });
            const data = await res.json();
            if (data.success) {
                setStatus({
                    type: 'success',
                    text: `Xabar muvaffaqiyatli tarqatildi! Yuborildi: ${data.success_count} ta, Xatolik: ${data.fail_count} ta.`
                });
                setMessage('');
            } else {
                setStatus({ type: 'error', text: 'Xatolik yuz berdi: ' + data.error });
            }
        } catch (e) {
            setStatus({ type: 'error', text: 'Aloqa xatoligi.' });
        } finally {
            setSending(false);
        }
    };

    return (
        <div>
            <Header title="Xabar yuborish" subtitle="Botdan ro'yxatdan o'tgan barcha foydalanuvchilarga ommaviy xabar yuborish" />
            
            <div className="section-card" style={{ maxWidth: '800px' }}>
                <h2 style={{ marginBottom: '16px' }}>Ommaviy xabar matni</h2>
                
                <form onSubmit={handleSend}>
                    <div style={{ marginBottom: '20px' }}>
                        <textarea 
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            disabled={sending}
                            rows={10}
                            placeholder="Xabar matnini kiriting... (HTML formatlash teglari qo'llab-quvvatlanadi: <b>qalin</b>, <i>kursiv</i>, <code>kod</code>, <a href='https://link.com'>havola</a>)"
                            style={{ 
                                width: '100%', 
                                backgroundColor: 'rgba(0, 0, 0, 0.2)', 
                                border: '1px solid var(--border-color)', 
                                borderRadius: '8px', 
                                color: 'var(--text-primary)', 
                                padding: '16px', 
                                fontSize: '15px',
                                fontFamily: 'inherit',
                                resize: 'vertical',
                                outline: 'none'
                            }}
                        />
                    </div>
                    
                    {status && (
                        <div style={{ 
                            padding: '12px 16px', 
                            borderRadius: '8px', 
                            marginBottom: '20px', 
                            fontSize: '14px',
                            fontWeight: '500',
                            backgroundColor: status.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : status.type === 'error' ? 'rgba(244, 63, 94, 0.1)' : 'rgba(59, 130, 246, 0.1)',
                            border: `1px solid ${status.type === 'success' ? 'var(--success-glow)' : status.type === 'error' ? 'var(--danger-glow)' : 'var(--accent-glow)'}`,
                            color: status.type === 'success' ? 'var(--success)' : status.type === 'error' ? 'var(--danger)' : 'var(--accent)'
                        }}>
                            {status.type === 'info' && <i className="fa-solid fa-spinner loading-spin" style={{ marginRight: '8px' }}></i>}
                            {status.type === 'success' && <i className="fa-solid fa-circle-check" style={{ marginRight: '8px' }}></i>}
                            {status.type === 'error' && <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '8px' }}></i>}
                            {status.text}
                        </div>
                    )}
                    
                    <button 
                        type="submit" 
                        disabled={sending}
                        style={{ 
                            backgroundColor: 'var(--accent)', 
                            border: 'none', 
                            color: '#fff', 
                            padding: '12px 24px', 
                            borderRadius: '8px', 
                            fontSize: '15px', 
                            fontWeight: '600', 
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            transition: 'opacity 0.2s',
                            opacity: sending ? 0.6 : 1
                        }}
                    >
                        {sending ? 'Yuborilmoqda...' : (
                            <React.Fragment>
                                <i className="fa-solid fa-paper-plane"></i>
                                Barchaga yuborish
                            </React.Fragment>
                        )}
                    </button>
                </form>
            </div>
        </div>
    );
}


// Chat Modal Component
function ChatModal({ user, messages, loading, onClose }) {
    const [activeSessionId, setActiveSessionId] = useState(null);

    // Get unique session IDs sorted in descending order (latest first)
    const sessions = Array.from(new Set(messages.map(m => m.session_id))).sort((a, b) => b - a);

    // Default to the first (latest) session when loaded
    useEffect(() => {
        if (sessions.length > 0 && activeSessionId === null) {
            setActiveSessionId(sessions[0]);
        }
    }, [sessions, activeSessionId]);

    // Filter messages for active session
    const activeMessages = messages.filter(m => m.session_id === activeSessionId);

    const renderedMessages = activeMessages.map(msg => (
        <div key={msg.id} className={`chat-message ${msg.role === 'user' ? 'user' : 'assistant'}`}>
            {msg.content}
            <span className="chat-time">{msg.created_at.split(' ')[1] || msg.created_at}</span>
        </div>
    ));

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h3>💬 {user.name} bilan AI suhbati</h3>
                    <button className="modal-close" onClick={onClose}>
                        <i className="fa-solid fa-xmark"></i>
                    </button>
                </div>
                
                <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
                    {/* Left Sidebar: Session List */}
                    <div style={{ 
                        width: '220px', 
                        borderRight: '1px solid var(--border-color)', 
                        overflowY: 'auto', 
                        backgroundColor: 'rgba(0,0,0,0.15)',
                        display: 'flex',
                        flexDirection: 'column'
                    }}>
                        <div style={{ 
                            padding: '12px 16px', 
                            fontSize: '12px', 
                            fontWeight: '600', 
                            color: 'var(--text-secondary)',
                            borderBottom: '1px solid var(--border-color)',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px'
                        }}>
                            Suhbatlar tarixi
                        </div>
                        {loading ? (
                            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '13px' }}>
                                <i className="fa-solid fa-spinner loading-spin" style={{ marginRight: '6px' }}></i>
                                Yuklanmoqda...
                            </div>
                        ) : sessions.length === 0 ? (
                            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '13px' }}>
                                Tarix topilmadi
                            </div>
                        ) : (
                            sessions.map(sid => (
                                <div 
                                    key={sid} 
                                    onClick={() => setActiveSessionId(sid)}
                                    style={{
                                        padding: '14px 16px',
                                        cursor: 'pointer',
                                        borderBottom: '1px solid rgba(255, 255, 255, 0.02)',
                                        backgroundColor: activeSessionId === sid ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                                        color: activeSessionId === sid ? 'var(--accent)' : 'var(--text-primary)',
                                        fontWeight: activeSessionId === sid ? '600' : '500',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '10px',
                                        transition: 'all 0.2s',
                                        fontSize: '13px'
                                    }}
                                >
                                    <i className="fa-solid fa-message" style={{ opacity: activeSessionId === sid ? 1 : 0.6 }}></i>
                                    <span>{sid}-sonli suhbat</span>
                                </div>
                            ))
                        )}
                    </div>
                    
                    {/* Right Pane: Chat Window */}
                    <div className="chat-container" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                        {loading ? (
                            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-secondary)' }}>
                                <i className="fa-solid fa-spinner loading-spin" style={{ marginRight: '8px', fontSize: '20px' }}></i>
                                Suhbat tarixi yuklanmoqda...
                            </div>
                        ) : sessions.length === 0 ? (
                            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-secondary)' }}>
                                Suhbat tarixi topilmadi.
                            </div>
                        ) : (
                            <React.Fragment>
                                <div className="chat-divider" style={{ margin: '0 auto 16px auto' }}>
                                    {activeSessionId}-sonli suhbat boshlangan
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1, overflowY: 'auto' }}>
                                    {renderedMessages}
                                </div>
                            </React.Fragment>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}


// Main App Component
function App() {
    const [currentTab, setCurrentTab] = useState('dashboard');
    const [stats, setStats] = useState({ active_users: 0, total_commands: 0 });
    const [users, setUsers] = useState([]);
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [chatUser, setChatUser] = useState(null);
    const [chatMessages, setChatMessages] = useState([]);
    const [loadingChat, setLoadingChat] = useState(false);
    const [lastUpdated, setLastUpdated] = useState('');

    const handleViewChat = async (userId, userName) => {
        setChatUser({ id: userId, name: userName });
        setChatMessages([]);
        setLoadingChat(true);
        try {
            const res = await fetch(`/api/chat_history?user_id=${userId}`);
            const data = await res.json();
            if (Array.isArray(data)) {
                setChatMessages(data);
            } else {
                console.error("Failed to load chat history:", data);
            }
        } catch (e) {
            console.error("Error loading chat history:", e);
        } finally {
            setLoadingChat(false);
        }
    };

    const fetchStats = async () => {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();
            if (!data.error) setStats(data);
        } catch (e) {
            console.error("Error fetching stats:", e);
        }
    };

    const fetchUsers = async () => {
        try {
            const res = await fetch('/api/users');
            const data = await res.json();
            if (!data.error) setUsers(data);
        } catch (e) {
            console.error("Error fetching users:", e);
        }
    };

    const fetchLogs = async () => {
        try {
            const res = await fetch('/api/logs');
            const data = await res.json();
            if (!data.error) setLogs(data);
        } catch (e) {
            console.error("Error fetching logs:", e);
        }
    };

    const refreshAll = async () => {
        setLoading(true);
        await Promise.all([fetchStats(), fetchUsers(), fetchLogs()]);
        setLoading(false);
        const now = new Date();
        setLastUpdated(now.toTimeString().split(' ')[0]);
    };

    useEffect(() => {
        refreshAll();
        // Auto-refresh stats and logs every 5 seconds
        const interval = setInterval(() => {
            fetchStats();
            fetchLogs();
            fetchUsers();
            const now = new Date();
            setLastUpdated(now.toTimeString().split(' ')[0]);
        }, 5000);
        return () => clearInterval(interval);
    }, []);

    const handleToggleBlock = async (userId, isBlocked) => {
        const actionText = isBlocked ? "bloklashni" : "blokdan chiqarishni";
        if (!confirm(`Haqiqatan ham ushbu foydalanuvchini ${actionText} istaysizmi?`)) {
            return;
        }
        try {
            setLoading(true);
            const res = await fetch('/api/users/block', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, is_blocked: isBlocked })
            });
            const data = await res.json();
            if (data.success) {
                alert(`Foydalanuvchi muvaffaqiyatli ${isBlocked ? "bloklandi" : "blokdan chiqarildi"}.`);
                await refreshAll();
            } else {
                alert("Xatolik: " + data.error);
            }
        } catch (e) {
            alert("Aloqada xatolik yuz berdi.");
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteUser = async (userId) => {
        if (!confirm("Haqiqatan ham ushbu foydalanuvchini, uning sessiyasi, barcha chatlar tarixi va loglarini butunlay o'chirib tashlamoqchimisiz?\nBu amalni ortga qaytarib bo'lmaydi!")) {
            return;
        }
        try {
            setLoading(true);
            const res = await fetch('/api/users/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            });
            const data = await res.json();
            if (data.success) {
                alert("Foydalanuvchi ma'lumotlari butunlay o'chirildi.");
                await refreshAll();
            } else {
                alert("Xatolik: " + data.error);
            }
        } catch (e) {
            alert("Aloqada xatolik yuz berdi.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <React.Fragment>
            <Sidebar currentTab={currentTab} setCurrentTab={setCurrentTab} />
            <div className="main-content">
                {currentTab === 'dashboard' && (
                    <DashboardView stats={stats} loading={loading} refreshData={refreshAll} setCurrentTab={setCurrentTab} lastUpdated={lastUpdated} />
                )}
                {currentTab === 'users' && (
                    <UsersView 
                        users={users} 
                        loading={loading} 
                        refreshData={refreshAll} 
                        onToggleBlock={handleToggleBlock}
                        onDeleteUser={handleDeleteUser}
                        lastUpdated={lastUpdated}
                    />
                )}
                {currentTab === 'logs' && (
                    <LogsView logs={logs} loading={loading} refreshData={refreshAll} onViewChat={handleViewChat} lastUpdated={lastUpdated} />
                )}
                {currentTab === 'broadcast' && (
                    <BroadcastView />
                )}
            </div>
            {chatUser && (
                <ChatModal 
                    user={chatUser} 
                    messages={chatMessages} 
                    loading={loadingChat} 
                    onClose={() => setChatUser(null)} 
                />
            )}
        </React.Fragment>
    );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
