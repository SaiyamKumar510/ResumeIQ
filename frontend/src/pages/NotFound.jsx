import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { EmptyState } from '../components/ui.jsx';

export default function NotFound() {
  return (
    <div className="card">
      <EmptyState icon={Compass} title="Page not found" text="The page you are looking for does not exist.">
        <Link to="/" className="btn btn-primary">Go to dashboard</Link>
      </EmptyState>
    </div>
  );
}
