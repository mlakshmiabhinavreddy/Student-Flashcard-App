// Global App Scripts
// Handles Sidebar Collapse and Mobile Menu

function toggleSidebarCollapse() {
    const sidebar = document.getElementById('sidebar');
    const container = document.querySelector('.app-container');
    const icon = document.getElementById('collapse-icon');
    
    if (sidebar.classList.contains('collapsed')) {
        sidebar.classList.remove('collapsed');
        if(container) container.classList.remove('sidebar-collapsed');
        // change icon back to left
        icon.setAttribute('data-lucide', 'chevron-left');
    } else {
        sidebar.classList.add('collapsed');
        if(container) container.classList.add('sidebar-collapsed');
        // change icon to right
        icon.setAttribute('data-lucide', 'chevron-right');
    }
    
    // Re-render the specific lucide icon that changed
    lucide.createIcons();
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('mobile-open');
}

// Ensure icons render on load
document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
});
