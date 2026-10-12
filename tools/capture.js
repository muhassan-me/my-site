// One listing manifest workflow for all event editions; page fetching stays in the local collector.
const bookmarklet = [
  'javascript:(()=>{',
  'const page=new URL(location.href),parts=page.pathname.split("/").filter(Boolean);',
  'let eventYear=0;',
  'const hostYear=page.hostname.split(".")[0];',
  'if(["2021","2022"].includes(hostYear))eventYear=Number(hostYear);',
  'for(const part of parts){const prefix="nasa-space-apps-",suffix="-local-events";const candidates=[part,part.startsWith(prefix)?part.slice(prefix.length):"",part.endsWith(suffix)?part.slice(0,-suffix.length):""];for(const value of candidates){const year=Number(value);if(Number.isInteger(year)&&year>=2023&&year<=new Date().getFullYear())eventYear=year}}',
  'if(!eventYear){const entered=prompt("Event edition year (2021 or later):","");if(entered===null)return;eventYear=Number(entered)}',
  'if(!Number.isInteger(eventYear)||eventYear<2021||eventYear>new Date().getFullYear()){alert("Capture failed: enter a valid event year.");return}',
  'const segments=page.pathname.split("/").filter(Boolean);',
  'const detailIndex=segments.findIndex((part,index)=>part==="locations"&&index<segments.length-1);',
  'const eventIndex=segments.findIndex((part,index)=>part.endsWith("local-events")&&index<segments.length-1);',
  'const isDetail=detailIndex>=0||eventIndex>=0;',
  'const roots=[...document.querySelectorAll("[id]")].filter(node=>/^(locations|local-events|\\d{4}-local-events)$/.test(node.id));',
  'const root=roots.find(node=>node.querySelector("a[href]"))||roots[0]||document;',
  'let locationUrls=[],locationCards=[];',
  'if(isDetail){locationUrls=[page.href]}else{',
  'for(const anchor of root.querySelectorAll("a[href]")){try{const target=new URL(anchor.href,page.href);if(target.hostname!==page.hostname)continue;const path=target.pathname.split("/").filter(Boolean);const hasLocationRoute=path.some((part,index)=>part==="locations"&&index<path.length-1);const card=anchor.closest("li[class*=local-event],article[class*=local-event],[data-location]");if(hasLocationRoute||card){locationUrls.push(target.href);locationCards.push({sourceUrl:target.href,text:(card||anchor).innerText||anchor.innerText})}}catch(error){}}',
  '}',
  'locationUrls=[...new Set(locationUrls)];',
  'const manifest={eventYear,sourceUrl:page.href,capturedAt:new Date().toISOString(),text:document.body.innerText,locationUrls,locationCards,discoveryStatus:locationUrls.length?"links-found":"no-detail-links-found"};',
  'const blob=new Blob([JSON.stringify(manifest,null,2)],{type:"application/json;charset=utf-8"});',
  'const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="space-apps-"+eventYear+"-locations.json";link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);',
  'if(locationUrls.length)alert("Saved "+locationUrls.length+" location URLs for edition "+eventYear+". Run the local collector with this manifest.");else alert("Saved the listing manifest, but no location detail links were present. The collection is incomplete; do not import listing text as location records.");',
  '})()'
].join('');

if (typeof module !== 'undefined' && module.exports) module.exports = bookmarklet;
