#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#define MASK 0xFFFFFFu
#define MAX_CELLS 32768
/* These are new, documented operational interpretations of conceptual PDFs,
   not algorithms claimed to be supplied by the source documents. */
typedef struct {uint32_t cells[MAX_CELLS];uint32_t stages[17];uint32_t stage_changes[17];uint64_t tick;uint32_t checksum;uint32_t flags;uint32_t dimension;uint32_t count;} HexState;
static uint32_t rot24(uint32_t x,unsigned n){n%=24;return n?((x<<n)|(x>>(24-n)))&MASK:(x&MASK);}
static uint32_t fold(HexState *s){uint32_t a=0;for(uint32_t i=0;i<s->count;i++)a=(a^rot24(s->cells[i],i%23+1))&MASK;return a;}
void hex_init(HexState *s,const uint32_t *values,size_t n,uint32_t dimension){memset(s,0,sizeof(*s));if(dimension<8||dimension>32)dimension=8;s->dimension=dimension;s->count=dimension*dimension*dimension;if(n==0)return;for(uint32_t i=0;i<s->count;i++)s->cells[i]=(values[i%n] ^ ((uint32_t)i*0x9E3779B9u))&MASK;s->checksum=fold(s);s->flags=1;}
void hex_step(HexState *s){
 uint32_t old[MAX_CELLS],next[MAX_CELLS];memcpy(old,s->cells,s->count*sizeof(uint32_t));uint32_t a=fold(s),d=0x45C881u,x=0x4BF981u;
 for(int stage=0;stage<17;stage++){
  memcpy(old,s->cells,s->count*sizeof(uint32_t));
  for(uint32_t i=0;i<s->count;i++){
   uint32_t v=old[i],left=old[(i%s->dimension==0)?i+s->dimension-1:i-1],right=old[(i%s->dimension==s->dimension-1)?i-s->dimension+1:i+1],up=old[(i+s->count-s->dimension*s->dimension)%s->count],down=old[(i+s->dimension*s->dimension)%s->count],out=v;
   switch(stage){
    case 0: out=(v+rot24(right,1))&MASK;break; /* late model */
    case 1: out=v;break; /* layout: positions are stable */
    case 2: out=(v ^ (uint32_t)(i*0x10101u))&MASK;break; /* location */
    case 3: out=(s->flags&1)?((v+((left^right)&0xFF))&MASK):v;break;
    case 4: out=(v+((left-right)&MASK))&MASK;break;
    case 5: out=v;break; /* operation control: no mutation */
    case 6: out=v;break; /* derived coordinates, no mutation */
    case 7: out=(v ^ rot24(left,3))&MASK;break;
    case 8: out=v;break; /* integration of runtime operation */
    case 9: out=v;break; /* integration of layout */
    case 10: out=(v+rot24(right^up^down,(unsigned)(i%7+1)))&MASK;break;
    case 11: out=(v^((left+right+up+down)&MASK))&MASK;break;
    case 12: out=v;break; /* file processing external */
    case 13: out=(v+d)&MASK;break; /* output hex example subtraction delta */
    case 14: out=(v^x)&MASK;break; /* input hex example XOR delta */
    case 15: out=rot24(v,1);break; /* repeat feedback */
    case 16: out=v;break; /* persistence external */
   }
   next[i]=out;
  }
  uint32_t changed=0;for(uint32_t j=0;j<s->count;j++)if(next[j]!=old[j])changed++;s->stage_changes[stage]=changed;memcpy(s->cells,next,s->count*sizeof(uint32_t));s->stages[stage]=fold(s);a^=s->stages[stage];
 }
 s->tick++;s->checksum=fold(s);
}
void hex_enable_extension(HexState *s,int enabled){if(enabled)s->flags|=1;else s->flags&=~1u;}

/* Optional state-changing RGB bond step. Simultaneous six-neighbor mixing.
   strength: 0..100; threshold: 0..100 (minimum RGB similarity).
   This is a configurable computational model, not vacuum physics. */
uint32_t hex_bond_step(HexState *s, uint32_t strength, uint32_t threshold){
 if(!s->count||!strength)return 0;
 if(strength>100)strength=100;if(threshold>100)threshold=100;
 uint32_t next[MAX_CELLS],n=s->dimension,changed=0;
 for(uint32_t i=0;i<s->count;i++){
  uint32_t z=i/(n*n),y=(i/n)%n,x=i%n,v=s->cells[i];
  uint32_t nb[6]={x?i-1:i,x+1<n?i+1:i,y?i-n:i,y+1<n?i+n:i,z?i-n*n:i,z+1<n?i+n*n:i};
  uint32_t sum[3]={0,0,0},bonds=0;
  for(int k=0;k<6;k++){
   if(nb[k]==i)continue;
   uint32_t w=s->cells[nb[k]],diff=0;
   for(int ch=0;ch<3;ch++){
    int a=(v>>(ch*8))&255,b=(w>>(ch*8))&255;
    diff+=(uint32_t)(a>b?a-b:b-a);
   }
   if((765-diff)*100<threshold*765)continue;
   for(int ch=0;ch<3;ch++)sum[ch]+=(w>>(ch*8))&255;
   bonds++;
  }
  uint32_t out=v;
  if(bonds){out=0;for(int ch=0;ch<3;ch++){
   uint32_t own=(v>>(ch*8))&255,avg=sum[ch]/bonds;
   uint32_t blended=(own*(100-strength)+avg*strength+50)/100;
   out|=(blended&255)<<(ch*8);
  }}
  next[i]=out;if(out!=v)changed++;
 }
 memcpy(s->cells,next,s->count*sizeof(uint32_t));s->checksum=fold(s);return changed;
}
int hex_set_cell(HexState *s,uint32_t index,uint32_t value){
 if(index>=s->count||value>MASK)return 0;
 s->cells[index]=value;s->checksum=fold(s);return 1;
}

/* RGB feedback filter: channel gain, applied to native state after every bond step. */
uint32_t hex_rgb_filter(HexState *s,uint32_t red,uint32_t green,uint32_t blue){
 uint32_t gains[3]={blue,green,red},changed=0;
 for(uint32_t i=0;i<s->count;i++){
  uint32_t v=s->cells[i],out=0;
  for(int ch=0;ch<3;ch++){
   uint32_t x=(v>>(ch*8))&255;
   uint32_t y=(x*gains[ch]+50)/100;if(y>255)y=255;
   out|=y<<(ch*8);
  }
  if(out!=v)changed++;s->cells[i]=out;
 }
 s->checksum=fold(s);return changed;
}

/* V7 A: conservative pairwise integer RGB flux. Each edge is visited once;
   exact per-channel sums are preserved by transferring integer units. */
uint32_t hex_separate_conservative(HexState *s, uint32_t rate){
 if(rate>100)rate=100;
 const uint32_t n=s->dimension,N=s->count;
 uint32_t next[MAX_CELLS]; memcpy(next,s->cells,N*sizeof(uint32_t));
 for(uint32_t i=0;i<N;i++){
  uint32_t x=i%n,y=(i/n)%n,z=i/(n*n);
  uint32_t js[3]={i+1,i+n,i+n*n};
  uint32_t valid[3]={x+1<n,y+1<n,z+1<n};
  for(int k=0;k<3;k++)if(valid[k]){
   uint32_t j=js[k];
   for(int ch=0;ch<3;ch++){
    uint32_t shift=8*ch, a=(s->cells[i]>>shift)&255u,b=(s->cells[j]>>shift)&255u;
    int delta=((int)a-(int)b)*(int)rate/1200;
    /* Clamp against current buffer so every intermediate channel stays 0..255. */
    int ai=(next[i]>>shift)&255, bj=(next[j]>>shift)&255;
    if(delta>0 && delta>ai)delta=ai;
    if(delta<0 && -delta>bj)delta=-bj;
    if(delta>0 && delta>255-bj)delta=255-bj;
    if(delta<0 && -delta>255-ai)delta=ai-255;
    ai-=delta;bj+=delta;
    next[i]=(next[i]&~(255u<<shift))|((uint32_t)ai<<shift);
    next[j]=(next[j]&~(255u<<shift))|((uint32_t)bj<<shift);
   }
  }
 }
 uint32_t changed=0;for(uint32_t i=0;i<N;i++)changed+=(next[i]!=s->cells[i]);
 memcpy(s->cells,next,N*sizeof(uint32_t));s->checksum=fold(s);return changed;
}
/* V7 B: deterministic per-cell channel transformation; nonconservative by design. */
uint32_t hex_separate_transform(HexState *s,uint32_t amplitude){
 if(amplitude>100)amplitude=100;
 uint32_t changed=0;
 for(uint32_t i=0;i<s->count;i++){
  uint32_t v=s->cells[i],out=0;
  for(int ch=0;ch<3;ch++){
   int a=(v>>(8*ch))&255;
   int wave=(int)((i*17u+s->tick*13u+(uint32_t)ch*71u)%21u)-10;
   int t=a+(wave*(int)amplitude)/100;
   if(t<0)t=0;if(t>255)t=255;
   out|=((uint32_t)t)<<(8*ch);
  }
  changed+=(out!=v);s->cells[i]=out;
 }
 s->checksum=fold(s);return changed;
}

/* V7.4: local RGB bonding + conservative directed nodal transport.
   Operates on the full native lattice, no persistent edge objects.
   Pairwise transfers preserve channel totals exactly, with 0..255 bounds.
   Bonding is symmetric mixing; transport is directional and tick-dependent.
   These are computational rules, not physical fluid mechanics. */
uint32_t hex_unified_dynamics(HexState *s,uint32_t bond_rate,uint32_t flow_rate){
 if(!s||!s->count)return 0;
 if(bond_rate>100)bond_rate=100;if(flow_rate>100)flow_rate=100;
 uint32_t n=s->dimension,N=s->count;
 uint32_t old[MAX_CELLS],next[MAX_CELLS];
 memcpy(old,s->cells,N*sizeof(uint32_t));memcpy(next,old,N*sizeof(uint32_t));
 for(uint32_t i=0;i<N;i++){
  uint32_t x=i%n,y=(i/n)%n,z=i/(n*n);
  uint32_t nb[3]={i+1,i+n,i+n*n};
  int valid[3]={x+1<n,y+1<n,z+1<n};
  for(int axis=0;axis<3;axis++)if(valid[axis]){
   uint32_t j=nb[axis];
   for(int ch=0;ch<3;ch++){
    uint32_t shift=ch*8,mask=255u<<shift;
    int a=(next[i]>>shift)&255,b=(next[j]>>shift)&255;
    int diff=a-b;
    /* Bond: equalize neighboring channels by a bounded integer flux. */
    int bond=(diff*(int)bond_rate)/800;
    /* Fluid: advect channel quantity along alternating directed edges. */
    int direction=((i+axis+ch+(uint32_t)s->tick)&1u)?1:-1;
    int flow=(int)flow_rate/25;
    int delta=bond+direction*flow;
    if(delta>a)delta=a;
    if(delta<-(b))delta=-b;
    if(delta< a-255)delta=a-255;
    if(delta>255-b)delta=255-b;
    a-=delta;b+=delta;
    next[i]=(next[i]&~mask)|((uint32_t)a<<shift);
    next[j]=(next[j]&~mask)|((uint32_t)b<<shift);
   }
  }
 }
 uint32_t changed=0;
 for(uint32_t i=0;i<N;i++)changed+=(next[i]!=old[i]);
 memcpy(s->cells,next,N*sizeof(uint32_t));s->checksum=fold(s);
 return changed;
}
