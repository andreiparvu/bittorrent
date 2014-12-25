#!/usr/bin/python

import sys
import bencode
import requests
import struct
import hashlib
import socket
import bitstring
from threading import Thread
import time

class Progress(Thread):
  def __init__(self):
    Thread.__init__(self)

  def run(self):
    while True:
      time.sleep(5)

      print "%d / %d" % (p + 1, nr_pieces)

      if p + 1 == nr_pieces:
        break


def getIP(values):
  r = []
  values = map(ord, values)
  for i in xrange(0, len(values), 6):
    r.append(('.'.join(map(str, values[i : i + 4])), values[i + 4] * 256 + values[i + 5]))
  return r

def getMesg(sock):
  length = struct.unpack_from(">I", sock.recv(4))[0]
  type = struct.unpack_from("B", sock.recv(1))

  allData = ""
  l = 1
  while l < length:
    cur = sock.recv(length - l)
    allData += cur

    l += len(cur)

  return (type[0], allData)


data = bencode.bdecode(open(sys.argv[1], "rb").read())

allLength = 0

print data['info'].keys()
piece_length = data['info']['piece length']
nr_pieces = len(data['info']['pieces']) / 20
print piece_length, nr_pieces

if 'files' in data['info']:
  for f in data['info']['files']:
    allLength += f['length']
else:
  allLength = data['info']['length']

payload = {
  'port': 6191,
  'uploaded': 0,
  'downloaded': 0,
  'compact': 1,
  'peer_id': '-TR2010-242123451231',
  'event': 'started',
  'left': allLength,
  'info_hash': hashlib.sha1(bencode.bencode(data['info'])).digest()
}

print payload

downloaded = ""
annList = []
if 'announce-list' in data:
  annList = map(lambda x: x[0], data['announce-list'])

prog = Progress()
prog.start()

for ip in [data['announce']] + annList:
  try:
    r = requests.get(ip, params = payload)

    peer_data = bencode.bdecode(r.text)

    msg = struct.pack("B19sII", 19, 'BitTorrent protocol', 0, 0) +\
      payload['info_hash'] + struct.pack("20s", payload['peer_id'])

    for client in getIP(peer_data['peers']):
      print client
      try:
        s = socket.socket()
        s.settimeout(2)
        s.connect(client)
        s.send(msg)

        reply = s.recv(10000)
        print struct.unpack_from("B", reply)
        print struct.unpack_from("20s", reply, 28)

        # print len(reply)
        # another = s.recv(10000)

        c = None
        while True:
          try:
            s.settimeout(0.5)
            m = getMesg(s)

            if m[0] == 5:
              print "once %d" % (len(m[1]) * 8)
              c = bitstring.BitArray(bytes = m[1], length = len(m[1]))
            elif m[0] == 4:
              c[struct.unpack_from(">I", m[1])[0]] = True
              print "ok"
          except Exception as e:
            # print e
            break
        # m2 = getMesg(s)
        # m3 = getMesg(s)
        # m4 = getMesg(s)
        # m5 = getMesg(s)

        # print m2[0]

        interested = struct.pack(">IB", 1, 2)
        # print struct.unpack(">IB", interested)
        s.send(interested)

        for p in xrange(nr_pieces):
          curPiece = ""
          for l in xrange(0, piece_length, 16384):
            curL = len(downloaded)
            limit = min(piece_length, l + 16384) - l
            limit = min(curL + limit, allLength) - curL

            if limit == 0:
              break
            # print curL + limit, allLength
            get = struct.pack(">IBIII", 13, 6, p, l, limit)

            while True:
              try:
                s.send(get)

                down = getMesg(s)

                if down[0] != 7:
                  if down[0] == 0:
                    unchoke = getMesg(s)

                    if unchoke[0] == 1:
                      continue
              except:
                continue

              break

            downloaded += down[1][8:]
            curPiece += down[1][8:]

            if curL + limit == allLength:
              print "da %d" % allLength
              break

          # print struct.unpack_from("20s", data['info']['pieces'][20 * p : 20 * p + 20])
          # print struct.unpack_from("20s", hashlib.sha1(curPiece).digest())
          # if data['info']['pieces'][20 * p : 20 * p + 20] != hashlib.sha1(curPiece).digest():
          #   print "problem"

        # print getMesg(s)

        # while True:
        #   print "one"
        #   another = s.recv(10000)
        #   print "hopa", another
        # for j in xrange(length[0] / 8):
          # print j
          # print struct.unpack_from("B", another, 5 + j)
        # print struct.unpack_from("B", another, 6)
        # print another
      except Exception as e:
        print e
        print "No valid handshake to %s" % client[0]
  except:
    continue
    # raise

print len(downloaded)
print peer_data

g = open("output", "wb")
g.write(downloaded)
g.close()