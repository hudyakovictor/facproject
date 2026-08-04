import { Kv } from "./ui";
export default function StructuredData({data}:{data:Record<string,unknown>|null}){
 if(!data)return <div className="muted">Нет данных</div>;
 const rows=Object.entries(data).filter(([,v])=>typeof v!=="object").map(([k,v])=>[k,v===null?"—":String(v)] as [string,string]);
 const nested=Object.entries(data).filter(([,v])=>v&&typeof v==="object");
 return <div className="stack"><Kv rows={rows}/>{nested.map(([k,v])=><details key={k}><summary>{k}</summary><pre className="code">{JSON.stringify(v,null,2)}</pre></details>)}</div>
}
