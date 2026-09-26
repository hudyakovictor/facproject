import React, { useRef } from 'react';

export default function DropZone({ label, photo, onPhotoSelect, badgeColor = '#0070f3' }) {
  const inputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onPhotoSelect(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      onPhotoSelect(e.target.files[0]);
    }
  };

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      onClick={() => inputRef.current.click()}
      style={{
        border: photo ? '1.5px solid #00ffaa' : '1.5px dashed #30363d',
        borderRadius: '12px',
        padding: '12px',
        background: photo ? 'rgba(0, 255, 170, 0.03)' : '#161b22',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '140px',
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        onChange={handleChange}
        style={{ display: 'none' }}
      />

      <div style={{
        position: 'absolute',
        top: '8px',
        left: '8px',
        background: badgeColor,
        color: '#fff',
        fontSize: '11px',
        fontWeight: 'bold',
        padding: '2px 8px',
        borderRadius: '6px',
        textTransform: 'uppercase'
      }}>
        {label}
      </div>

      {photo ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', width: '100%' }}>
          <img
            src={URL.createObjectURL(photo)}
            alt="Preview"
            style={{ width: '80px', height: '80px', objectFit: 'cover', borderRadius: '8px', marginTop: '16px' }}
          />
          <span style={{ fontSize: '12px', color: '#8b949e', maxWidth: '140px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
            {photo.name}
          </span>
        </div>
      ) : (
        <div style={{ textAlign: 'center', color: '#8b949e', fontSize: '13px', marginTop: '14px' }}>
          <div style={{ fontSize: '28px', marginBottom: '6px' }}>📷</div>
          <span>Нажмите или перетащите фото</span>
        </div>
      )}
    </div>
  );
}
