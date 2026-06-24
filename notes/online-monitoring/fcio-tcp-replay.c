/* Replay a real .fcio file as a live TCP stream (tmio/fcio).
   usage: fcio_replay <infile.fcio> <tcp://listen/PORT> [sleep_us_per_event] */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "fcio.h"

int main(int argc, char** argv){
  if (argc < 3){ fprintf(stderr,"usage: %s in.fcio tcp://listen/PORT [sleep_us]\n",argv[0]); return 2; }
  const char* infile = argv[1];
  const char* outpeer = argv[2];
  int sleep_us = argc>3 ? atoi(argv[3]) : 0;

  FCIOData* in = FCIOOpen(infile, 0, 0);
  if (!in){ fprintf(stderr,"cannot open input %s\n", infile); return 1; }
  FCIOStream out = FCIOConnect(outpeer, 'w', -1, 0);   /* block for connection */
  if (!out){ fprintf(stderr,"cannot open output %s\n", outpeer); return 1; }
  fprintf(stderr,"[replay] connected, streaming %s -> %s\n", infile, outpeer);

  int tag, n=0;
  while ((tag = FCIOGetRecord(in)) > 0){
    FCIOPutRecord(out, in, tag);
    n++;
    if (sleep_us>0 && (tag==3 || tag==6)) usleep(sleep_us); /* pace events */
  }
  fprintf(stderr,"[replay] done, %d records sent, closing\n", n);
  FCIODisconnect(out);
  FCIOClose(in);
  return 0;
}
