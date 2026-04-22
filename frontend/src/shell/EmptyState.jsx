export default function EmptyState({ title, description, action }) {
  return (
    <div className="panel empty-state" style={{ marginTop: 20 }}>
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {action || null}
    </div>
  );
}
