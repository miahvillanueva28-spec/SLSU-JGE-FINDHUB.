{% extends "base.html" %}
{% block title %}Admin Dashboard — SLSU JGE FindHub{% endblock %}

{% block head %}
<style>
.dashboard-wrapper {
  max-width: 1400px;
  margin: 0 auto;
  padding: 1.5rem;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-radius: 16px;
  border: 1px solid rgba(7, 92, 59, 0.12);
}

.page-title h1 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  color: #055c34;
  font-weight: 800;
}

.page-title p {
  margin: 0;
  color: #557563;
  font-size: 0.95rem;
}

.export-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: linear-gradient(135deg, #075c3b, #087443);
  color: #ffffff;
  padding: 0.75rem 1.5rem;
  border-radius: 12px;
  text-decoration: none;
  font-weight: 600;
  transition: all 0.3s ease;
}

.export-btn:hover {
  transform: translateY(-2px);
}

.stats-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.stat-card {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(16px);
  border-radius: 16px;
  padding: 1.2rem;
  border: 1px solid rgba(7, 92, 59, 0.12);
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(7, 92, 59, 0.08);
}

.stat-label {
  font-size: 0.85rem;
  color: #668072;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.stat-number {
  font-size: 1.5rem;
  font-weight: 800;
  color: #1a3024;
}

.stat-card.lost .stat-number { color: #c0392b; }
.stat-card.found .stat-number { color: #27ae60; }
.stat-card.open .stat-number { color: #2980b9; }
.stat-card.pending .stat-number { color: #f39c12; }
.stat-card.returned .stat-number { color: #27ae60; }
.stat-card.archived .stat-number { color: #7f8c8d; }

.actions-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 2rem;
  padding: 1.25rem;
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(16px);
  border-radius: 16px;
  border: 1px solid rgba(7, 92, 59, 0.12);
}

.main-action-btn {
  background: linear-gradient(135deg, #075c3b, #087443);
  color: #fff;
  padding: 0.8rem 1.6rem;
  border-radius: 12px;
  text-decoration: none;
  font-weight: 600;
  transition: all 0.3s ease;
}

.main-action-btn:hover {
  transform: translateY(-2px);
}

.badge-dot {
  background: rgba(255,255,255,0.25);
  padding: 0.2rem 0.6rem;
  border-radius: 20px;
  margin-left: 0.5rem;
  font-size: 0.8rem;
}

.filter-group {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.filter-btn, .history-btn, .clear-btn {
  padding: 0.7rem 1.2rem;
  border-radius: 10px;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.9rem;
  border: 1px solid transparent;
  transition: all 0.3s ease;
}

.filter-btn {
  background: rgba(255, 255, 255, 0.7);
  border-color: rgba(7, 92, 59, 0.15);
  color: #2d4a3b;
}

.filter-btn:hover {
  background: rgba(7, 92, 59, 0.08);
}

.filter-btn.active {
  background: #075c3b;
  color: #fff;
  border-color: #075c3b;
}

.history-btn {
  background: rgba(254, 243, 199, 0.8);
  color: #92400e;
}

.history-btn:hover {
  background: rgba(253, 230, 138, 0.9);
}

.clear-btn {
  background: rgba(7, 92, 59, 0.08);
  color: #075c3b;
}

.table-wrapper {
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(16px);
  border-radius: 20px;
  border: 1px solid rgba(7, 92, 59, 0.12);
  overflow: hidden;
}

.table-heading {
  padding: 1.5rem;
  border-bottom: 1px solid rgba(7, 92, 59, 0.08);
}

.table-heading h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: #1a3024;
}

.table-head-row {
  display: grid;
  grid-template-columns: 65px 2fr 100px 140px 160px 110px 130px;
  gap: 0.5rem;
  padding: 1rem 1.5rem;
  background: rgba(7, 92, 59, 0.04);
  font-weight: 700;
  color: #557563;
  border-bottom: 1px solid rgba(7, 92, 59, 0.08);
}

.table-data-row {
  display: grid;
  grid-template-columns: 65px 2fr 100px 140px 160px 110px 130px;
  gap: 0.5rem;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid rgba(7, 92, 59, 0.05);
  align-items: center;
  transition: background 0.25s ease;
}

.table-data-row:hover {
  background: rgba(7, 92, 59, 0.03);
}

.col-id {
  color: #7a9485;
  font-family: monospace;
  font-weight: 600;
}

.item-link {
  color: #075c3b;
  text-decoration: none;
  font-weight: 600;
  transition: color 0.2s ease;
}

.item-link:hover {
  text-decoration: underline;
  color: #055c34;
}

.type-lost { color: #c0392b; font-weight: 600; }
.type-found { color: #27ae60; font-weight: 600; }

.stat-open { color: #2980b9; font-weight: 600; }
.stat-pending-claim { color: #f39c12; font-weight: 600; }
.stat-returned { color: #27ae60; font-weight: 600; }
.stat-archived { color: #7f8c8d; font-weight: 600; }

.sel-form select {
  width: 100%;
  padding: 0.5rem 0.6rem;
  border: 1.5px solid rgba(7, 92, 59, 0.18);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  cursor: pointer;
  font-weight: 500;
}

.sel-form select:focus {
  outline: none;
  border-color: #075c3b;
}

.col-date {
  color: #668072;
  font-size: 0.85rem;
}

.action-set {
  display: flex;
  gap: 0.4rem;
}

.view-btn {
  background: rgba(7, 92, 59, 0.08);
  color: #075c3b;
  padding: 0.5rem 0.8rem;
  border-radius: 7px;
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 600;
  transition: all 0.25s ease;
}

.view-btn:hover {
  background: rgba(7, 92, 59, 0.15);
}

.del-form {
  margin: 0;
}

.del-btn {
  background: rgba(220, 53, 69, 0.08);
  color: #c0392b;
  padding: 0.5rem 0.8rem;
  border-radius: 7px;
  border: none;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s ease;
}

.del-btn:hover {
  background: rgba(220, 53, 69, 0.15);
}

.empty-box {
  padding: 3rem;
  text-align: center;
  color: #668072;
}

@media (max-width: 900px) {
  .top-bar {
    flex-direction: column;
    align-items: flex-start;
  }
  .table-head-row,
  .table-data-row {
    grid-template-columns: 1fr 1fr;
    gap: 0.8rem 1rem;
  }
  .col-id, .col-date { display: none; }
  .actions-wrapper { flex-direction: column; align-items: stretch; }
  .filter-group { justify-content: center; }
}

@media (max-width: 550px) {
  .stats-container { grid-template-columns: 1fr 1fr; }
}
</style>
{% endblock %}

{% block content %}
<div class="dashboard-wrapper">

  <!-- TOP HEADER -->
  <div class="top-bar">
    <div class="page-title">
      <h1>Admin Dashboard</h1>
      <p>Manage reports, review claims, and update item statuses</p>
    </div>
    <a href="{{ url_for('export_reports') }}" class="export-btn">Export CSV</a>
  </div>

  <!-- STATS -->
  <div class="stats-container">
    <div class="stat-card">
      <p class="stat-label">Total Reports</p>
      <p class="stat-number">{{ stats.total }}</p>
    </div>
    <div class="stat-card lost">
      <p class="stat-label">Lost Items</p>
      <p class="stat-number">{{ stats.lost }}</p>
    </div>
    <div class="stat-card found">
      <p class="stat-label">Found Items</p>
      <p class="stat-number">{{ stats.found }}</p>
    </div>
    <div class="stat-card open">
      <p class="stat-label">Open</p>
      <p class="stat-number">{{ stats.open }}</p>
    </div>
    <div class="stat-card pending">
      <p class="stat-label">Pending Claims</p>
      <p class="stat-number">{{ stats.pending_claims }}</p>
    </div>
    <div class="stat-card returned">
      <p class="stat-label">Returned</p>
      <p class="stat-number">{{ stats.returned }}</p>
    </div>
    <div class="stat-card archived">
      <p class="stat-label">Archived</p>
      <p class="stat-number">{{ stats.archived }}</p>
    </div>
  </div>

  <!-- ACTIONS -->
  <div class="actions-wrapper">
    <a href="{{ url_for('admin_claims') }}" class="main-action-btn">
      Review Claims
      {% if stats.pending_claims > 0 %}
        <span class="badge-dot">{{ stats.pending_claims }}</span>
      {% endif %}
    </a>
    <div class="filter-group">
      <a href="{{ url_for('admin_dashboard') }}?filter=Lost" 
         class="filter-btn {% if request.args.get('filter') == 'Lost' %}active{% endif %}">Lost Only</a>
      <a href="{{ url_for('admin_dashboard') }}?filter=Found" 
         class="filter-btn {% if request.args.get('filter') == 'Found' %}active{% endif %}">Found Only</a>
      <a href="{{ url_for('admin_history') }}" class="history-btn">Deleted</a>
      {% if request.args.get('filter') %}
        <a href="{{ url_for('admin_dashboard') }}" class="clear-btn">Show All</a>
      {% endif %}
    </div>
  </div>

  <!-- REPORTS TABLE -->
  <div class="table-wrapper">
    <div class="table-heading">
      <h2>
        {% if request.args.get('filter') == 'Lost' %}Lost Reports
        {% elif request.args.get('filter') == 'Found' %}Found Reports
        {% else %}All Reports{% endif %}
      </h2>
    </div>

    {% if reports %}
      <div>
        <div class="table-head-row">
          <span class="col-id">ID</span>
          <span>Item Name</span>
          <span>Type</span>
          <span>Status</span>
          <span>Update Status</span>
          <span>Date</span>
          <span>Actions</span>
        </div>

        {% for report in reports %}
          {% set current_filter = request.args.get('filter') %}
          {% if not current_filter or current_filter == report.report_type %}
          <div class="table-data-row">
            <span class="col-id">#{{ report.id }}</span>
            <a href="{{ url_for('report_detail', report_id=report.id) }}" class="item-link">
              {{ report.item_name }}
            </a>
            <span class="type-{{ report.report_type|lower }}">
              {{ report.report_type }}
            </span>
            <span class="stat-{{ report.status|replace(' ', '-')|lower }}">
              {{ report.status }}
            </span>
            <form action="{{ url_for('admin_update_report_status', report_id=report.id) }}" method="POST" class="sel-form">
              <select name="status" onchange="this.form.submit()">
                <option value="Open" {% if report.status == 'Open' %}selected{% endif %}>Open</option>
                <option value="Pending Claim" {% if report.status == 'Pending Claim' %}selected{% endif %}>Pending Claim</option>
                <option value="Returned" {% if report.status == 'Returned' %}selected{% endif %}>Returned</option>
                <option value="Archived" {% if report.status == 'Archived' %}selected{% endif %}>Archived</option>
              </select>
            </form>
            <span class="col-date">{{ report.created_at.strftime('%Y-%m-%d') }}</span>
            <div class="action-set">
              <a href="{{ url_for('report_detail', report_id=report.id) }}" class="view-btn">View</a>
              <form action="{{ url_for('admin_delete_report', report_id=report.id) }}" method="POST" class="del-form"
                    onsubmit="return confirm('Delete this report?');">
                <button type="submit" class="del-btn">Delete</button>
              </form>
            </div>
          </div>
          {% endif %}
        {% endfor %}
      </div>
    {% else %}
      <div class="empty-box">
        <p>No reports found.</p>
      </div>
    {% endif %}
  </div>

</div>
{% endblock %}
