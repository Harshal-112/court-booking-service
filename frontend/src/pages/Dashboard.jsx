import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../services/api";
import { ChevronRight, ExternalLink, RefreshCw, Search, Building2, Plane, Check, Clock, Wallet, Download } from "lucide-react";

function formatDate(dt) {
  const d = new Date(dt);
  return d.toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "numeric", minute: "2-digit", hour12: false,
  });
}

function formatDateTime(startsAt) {
  const d = new Date(startsAt);
  return d.toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

function StatusBadge({ status }) {
  const labels = {
    confirmed: "Confirmed",
    held: "Hold",
    cancelled: "Cancelled",
    expired: "Expired",
  };
  const colors = {
    confirmed: "bg-green-500/20 text-green-700 dark:text-green-300 border-green-500/30",
    held: "bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-500/30",
    cancelled: "bg-red-500/20 text-red-700 dark:text-red-300 border-red-500/30",
    expired: "bg-gray-500/20 text-gray-600 dark:text-gray-300 border-gray-500/30",
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium border ${colors[status] || "bg-gray-500/20 text-gray-600"}`}>
      {labels[status] || status}
    </span>
  );
}

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [stats, setStats] = useState({ upcoming_bookings: 0, total_bookings: 0, refunds: 0, wallet_balance: 0 });
  const [bookings, setBookings] = useState([]);
  const [upcomingBookings, setUpcomingBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFilter, setDateFilter] = useState("");
  const [courtSearch, setCourtSearch] = useState("");

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    setLoading(true);
    setError("");
    try {
      const [statsRes, bookRes] = await Promise.all([
        api.get("/dashboard/stats"),
        api.get("/dashboard/bookings"),
        api.get("/dashboard/bookings/upcoming"),
      ]);
      setStats(statsRes);
      setBookings(bookRes);
      setUpcomingBookings(bookRes);
    } catch (err) {
      if (err.name === "ApiError") {
        setError(err.message);
      } else {
        setError("Failed to load dashboard data.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    await fetchData();
  }

  async function handleCourtSearch(e) {
    const q = e.target.value.toLowerCase();
    setCourtSearch(q);
    setBookings(prev => prev.filter(b =>
      (`${b.court_name} ${b.sport_type}`).toLowerCase().includes(q)
    ));
  }

  async function handleExport() {
    const rows = ["ID", "Court", "Venue", "Sport", "Starts At", "Ends At", "Price", "Status", "Refund"];
    const header = rows.join(",");
    const dataLines = bookings.map(b => [
      String(b.id), `"${b.court_name}"`, `"${b.venue_name}"`, `"${b.sport_type}"`,
      `"${formatDateTime(b.starts_at)}"`, `"${formatDateTime(b.ends_at)}"`, String(b.price),
      `"${b.status}"`, b.refund_eligible ? 'true' : 'false'
    ].join(","));
    const csv = [header, ...dataLines].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `bookings_${user.email.split("@")[0]}.csv`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function handleCancel(bookingId) {
    try {
      await api.post(`/bookings/${bookingId}/cancel`);
      await fetchData();
    } catch (err) {
      alert(err.name === "ApiError" ? err.message : "Failed to cancel booking.");
    }
  }

  const statsCards = [
    { key: "upcoming_bookings", label: "Upcoming Bookings", icon: Clock, color: "#3b82f6" },
    { key: "total_bookings", label: "Total Bookings", icon: Building2, color: "#ef4444" },
    { key: "refunds", label: "Refunds", icon: Plane, color: "#f97316" },
    { key: "wallet_balance", label: "Wallet Balance", icon: Wallet, color: "#22c55e" },
  ];

  const tabLabels = ["All", "Upcoming", "Confirmed", "Cancelled", "Refunds"];
  const activeTab = tabLabels.indexOf(statusFilter === "" ? "All" : statusFilter) >= 0 ? "All" : statusFilter;
  const filteredBookings = activeTab === "Upcoming" ? upcomingBookings :
    activeTab === "Confirmed" ? bookings.filter(b => b.status === "confirmed") :
    activeTab === "Cancelled" ? bookings.filter(b => b.status === "cancelled") :
    activeTab === "Refunds" ? bookings.filter(b => b.refund_eligible) : bookings;

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-black">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Dashboard</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Welcome back, <span className="font-medium">{user?.full_name}</span>. Manage your court bookings.
            </p>
          </div>
          <button onClick={logout} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 text-white hover:bg-slate-700 transition">
            <ExternalLink size={16} /> Logout
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-950/50 border border-red-500/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        {/* Quick Actions */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <QuickAction icon={Plane} label="Book a Court" subtitle="Find available courts and book now" color="#3b82f6" onClick={() => window.open(`#/book-a-court`, "_self")}>
            Book a Court
          </QuickAction>
          <QuickAction icon={Clock} label="Show Available Courts" subtitle="Check court availability for today" color="#8b5cf6" onClick={() => window.open(`#/show-courts`, "_self")}>
            Show Available Courts
          </QuickAction>
          <QuickAction icon={Download} label="Export Bookings" subtitle="Download your booking history as CSV" color="#ec4899" onClick={handleExport} />
          <QuickAction icon={RefreshCw} label="Refresh Data" subtitle="Reload dashboard statistics" color="#14b8a6" onClick={handleRefresh} />
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {statsCards.map(card => (
            <div key={card.key} className="rounded-xl bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 p-5 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${card.color}1A` }}>
                  <card.icon size={20} style={{ color: card.color }} />
                </div>
              </div>
              <p className="text-sm text-slate-500 dark:text-slate-400">{card.label}</p>
              <p className="text-2xl font-bold mt-1" style={{ color: card.color }}>{stats[card.key]}</p>
            </div>
          ))}
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Booking History */}
          <div className="lg:col-span-2">
            <div className="rounded-xl bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 overflow-hidden shadow-sm">
              {/* Section Header */}
              <div className="p-5 border-b border-slate-100 dark:border-slate-700 flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Booking History</h2>
                  <span className="text-sm text-slate-500 dark:text-slate-400">{filteredBookings.length} items</span>
                </div>
                <div className="flex items-center gap-3 flex-wrap">
                  <input type="search" placeholder="Search courts..." value={courtSearch} onChange={handleCourtSearch}
                    className="pl-9 pr-3 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-700 text-sm border border-slate-200 dark:border-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/30 w-48 sm:w-64" />
                </div>
              </div>

              {/* Filter Tabs */}
              <div className="flex p-3 border-b border-slate-100 dark:border-slate-700 flex-wrap gap-1">
                {tabLabels.map(tab => (
                  <button key={tab} onClick={() => setStatusFilter(tab)}
                    className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${statusFilter === tab ? "bg-blue-600 text-white" : "bg-slate-50 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-600"}`}>
                    {tab}
                  </button>
                ))}
              </div>

              {/* Bookings List */}
              {loading ? (
                <div className="p-8 flex items-center justify-center text-slate-400">Loading...</div>
              ) : filteredBookings.length === 0 ? (
                <div className="p-8 text-center text-slate-400">
                  <Search size={40} className="mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No bookings found.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-700/50 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                        <th className="px-4 py-2.5">Court</th>
                        <th className="px-4 py-2.5 hidden sm:table-cell">Start</th>
                        <th className="px-4 py-2.5 hidden sm:table-cell">End</th>
                        <th className="px-4 py-2.5 hidden md:table-cell">Venue</th>
                        <th className="px-4 py-2.5">Status</th>
                        <th className="px-4 py-2.5 hidden md:table-cell">Price</th>
                        <th className="px-4 py-2.5"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredBookings.slice(0, 50).map(booking => (
                        <tr key={booking.id} className="border-t border-slate-50 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                          <td className="px-4 py-3 align-top">
                            <div className="font-medium text-slate-900 dark:text-white text-sm">{booking.court_name}</div>
                            <div className="text-xs text-slate-500 dark:text-slate-400">{booking.sport_type}</div>
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-300 whitespace-nowrap hidden sm:table-cell">
                            {formatDate(booking.starts_at)}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-300 whitespace-nowrap hidden sm:table-cell">
                            {formatDateTime(booking.ends_at)}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-500 dark:text-slate-400 hidden md:table-cell max-w-[120px] truncate">{booking.venue_name}</td>
                          <td className="px-4 py-3"><StatusBadge status={booking.status} /></td>
                          <td className="px-4 py-3 text-sm font-mono text-slate-700 dark:text-slate-200 hidden md:table-cell">${Number(booking.price).toFixed(2)}</td>
                          <td className="px-4 py-3 flex items-center gap-1">
                            {booking.status !== "confirmed" && (
                              <button onClick={() => handleCancel(booking.id)} className="p-1.5 rounded text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors">
                                <Check size={14} />
                              </button>
                            )}
                            {booking.status !== "cancelled" && booking.status !== "expired" && (
                              <span className="text-xs text-slate-400" title="View details">
                                <ChevronRight size={14} />
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filteredBookings.length > 50 && (
                    <div className="p-3 text-center text-sm text-slate-500">Showing 50 of {filteredBookings.length} bookings</div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Upcoming Booking Details */}
          <div>
            <div className="rounded-xl bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 overflow-hidden shadow-sm">
              <div className="p-5 border-b border-slate-100 dark:border-slate-700 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Upcoming Bookings</h2>
                <span className="text-sm text-slate-500 dark:text-slate-400">{upcomingBookings.length} items</span>
              </div>

              {loading ? (
                <div className="p-8 flex items-center justify-center text-slate-400">Loading...</div>
              ) : upcomingBookings.length === 0 ? (
                <div className="p-8 text-center text-slate-400">
                  <Plane size={40} className="mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No upcoming bookings.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {upcomingBookings.slice(0, 5).map(booking => (
                    <div key={booking.id} className="p-4 border border-slate-100 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-slate-900 dark:text-white text-sm">{booking.court_name}</span>
                            <StatusBadge status={booking.status} />
                          </div>
                          <p className="text-xs text-slate-500 dark:text-slate-400">
                            <Building2 size={12} className="mr-1 inline" /> {booking.venue_name}
                          </p>
                          <p className="text-xs text-slate-500 dark:text-slate-400">
                            <Clock size={12} className="mr-1 inline" /> {formatDate(booking.starts_at)} – {formatDateTime(booking.ends_at)}
                          </p>
                        </div>
                        <div className="text-right ml-4">
                          <div className="font-bold text-slate-900 dark:text-white">${Number(booking.price).toFixed(2)}</div>
                          <button onClick={() => window.open(`#/booking/${booking.id}`, "_self")}
                            className="mt-1 px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors inline-flex items-center gap-1">
                            View Details <ChevronRight size={12} />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Calendar Link */}
            <div className="mt-4 rounded-xl bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 overflow-hidden shadow-sm">
              <div className="p-5 border-b border-slate-100 dark:border-slate-700 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Calendar</h2>
              </div>
              <div className="p-6 flex flex-col items-center justify-center text-center">
                <div className="mb-2 px-3 py-1.5 rounded-full bg-blue-600 text-white text-xs font-medium">Weekly Court Availability</div>
                <p className="text-sm text-slate-600 dark:text-slate-300">View your court availability for this week</p>
                <button onClick={() => window.open(`#/calendar`, "_self")}
                  className="mt-3 px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-700 transition">
                  Open Week View
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function QuickAction({ icon: Icon, label, subtitle, color, onClick }) {
  return (
    <div className="rounded-xl bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 p-4 shadow-sm hover:shadow-md transition-shadow cursor-pointer" onClick={onClick}>
      <Icon size={20} color={color} />
      <p className="font-medium text-slate-900 dark:text-white text-sm mt-2">{label}</p>
      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</p>
    </div>
  );
}
