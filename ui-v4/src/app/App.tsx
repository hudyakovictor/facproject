import { useState } from "react";
import TimelineView from "../features/timeline/TimelineView";
import DataManager from "../features/data-manager/DataManager";
import SettingsPage from "../features/settings/SettingsPage";
import PhotoPage from "../features/photo-lab/PhotoPage";
import ProfilesPage from "../features/profiles/ProfilesPage";

type View = "timeline" | "data" | "profiles" | "settings";
export default function App(){
  const [view,setView]=useState<View>("timeline");
  const [photoId,setPhotoId]=useState<string|null>(null);
  const openPhoto=(id:string)=>{setPhotoId(id)};
  const closePhoto=()=>{setPhotoId(null)};
  return <div className="root-shell">
    <aside className="app-nav">
      <div className="nav-logo"><i>D</i><span>V4</span></div>
      <nav>
        <button className={view==="timeline"?"active":""} onClick={()=>setView("timeline")} title="Timeline"><span>⌁</span><b>Timeline</b></button>
        <button className={view==="data"?"active":""} onClick={()=>setView("data")} title="Data Manager"><span>▦</span><b>Data Manager</b></button>
        <button className={view==="profiles"?"active":""} onClick={()=>setView("profiles")} title="Profiles"><span>▣</span><b>Profiles</b></button>
        <button className={view==="settings"?"active":""} onClick={()=>setView("settings")} title="Настройки"><span>⚙</span><b>Settings</b></button>
        <button className={photoId!==null?"active":""} onClick={()=>setPhotoId("")} title="Фото"><span>◫</span><b>Photo Lab</b></button>
      </nav>
      <small>APP6<br/>CONTROL</small>
    </aside>
    <div className="app-content">
      {view==="timeline"&&<TimelineView openPhoto={openPhoto}/>} 
      {view==="data"&&<DataManager/>}
      {view==="profiles"&&<ProfilesPage/>}
      {view==="settings"&&<SettingsPage openPhoto={openPhoto}/>} 
    </div>
    {photoId!==null&&(
      <div className="photo-modal-backdrop" onClick={closePhoto}>
        <div className="photo-modal" onClick={e=>e.stopPropagation()}>
          <button className="photo-modal-close" onClick={closePhoto} title="Закрыть">×</button>
          <PhotoPage initialId={photoId} />
        </div>
      </div>
    )}
  </div>
}
