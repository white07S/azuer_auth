import React from 'react';
import { NavLink } from 'react-router-dom';
import { User, LogOut, LogIn } from 'lucide-react';

const Header = ({ isAuthenticated, userInfo, onLogin, onLogout, navItems }) => {
  return (
    <header className="app-header">
      <div className="header-container">
        <div className="header-logo">
          <h1>Azure AI Chat</h1>
        </div>

        <nav className="header-nav">
          {isAuthenticated && navItems?.length > 0 && (
            <ul className="nav-list">
              {navItems.map((item) => (
                <li key={item.key}>
                  <NavLink
                    to={item.path}
                    className={({ isActive }) =>
                      `nav-link${isActive ? ' nav-link-active' : ''}`
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          )}

          {isAuthenticated ? (
            <div className="user-menu">
              <div className="user-info">
                <User size={18} />
                <span>{userInfo?.user_email || 'User'}</span>
                {userInfo?.roles && userInfo.roles.length > 0 && (
                  <span className="user-role">({userInfo.roles[0]})</span>
                )}
              </div>
              <button onClick={onLogout} className="btn-icon" title="Sign Out">
                <LogOut size={18} />
              </button>
            </div>
          ) : (
            <button onClick={onLogin} className="btn-primary btn-header">
              <LogIn size={18} />
              <span>Sign In</span>
            </button>
          )}
        </nav>
      </div>
    </header>
  );
};

export default Header;
