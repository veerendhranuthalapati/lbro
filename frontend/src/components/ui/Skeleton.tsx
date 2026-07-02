interface Props { style?: React.CSSProperties; height?: number | string; width?: number | string }

export function Skeleton({ style, height = 16, width = '100%' }: Props) {
  return (
    <div style={{
      height,
      width,
      background: 'linear-gradient(90deg, #e8e2d9 25%, #f0ebe2 50%, #e8e2d9 75%)',
      backgroundSize: '200% 100%',
      animation: 'shimmer 1.4s infinite',
      borderRadius: 4,
      ...style,
    }} />
  )
}

export function IncidentCardSkeleton() {
  return (
    <div style={{ background: '#f9f5ef', border: '1px solid #c8c2b8', borderRadius: 4, padding: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <Skeleton width={60} height={12} />
        <Skeleton width={80} height={12} />
      </div>
      <Skeleton width="75%" height={14} />
      <Skeleton width="100%" height={12} />
      <div style={{ display: 'flex', gap: 6 }}>
        <Skeleton width={56} height={18} />
        <Skeleton width={56} height={18} />
      </div>
      <style>{`@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>
    </div>
  )
}
