import concurrent.futures
import http.client
import json
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from server import ApiError, KST, Store, make_server


class BookingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'booking.sqlite'
        self.store=Store(self.path,lambda:datetime(2026,10,13,9,tzinfo=KST))
        self.people=[dict(name='대표',studentId='20260001'),dict(name='동반',studentId='20260002')]
    def tearDown(self): self.tmp.cleanup()
    def general(self,**kwargs):
        data=dict(kind='general',name='대표',studentId='20260001',attendees=self.people,
                  periodStart='2026-10-14',periodEnd='2026-10-14',startTime='14:00',endTime='16:00',password='booking-password')
        data.update(kwargs)
        return data
    def regular(self,**kwargs):
        data=self.general(kind='regular',groupName='스터디',contact='01000000000',purpose='공부',
                          periodStart='2026-10-13',periodEnd='2026-10-31',weekdays=['수'])
        data.update(kwargs)
        return data
    def assert_api(self,status,fn):
        with self.assertRaises(ApiError) as ctx: fn()
        self.assertEqual(status,ctx.exception.status)
    def edit_data(self,b,**kwargs):
        data=dict(action='edit',version=b['version'],name=b['name'],studentId=b['student_id'],
                  attendees=b['attendees'],groupName=b['group_name'],contact=b['contact'],purpose=b['purpose'],
                  periodStart=b['period_start'],periodEnd=b['period_end'],weekdays=b['weekdays'],
                  startTime=b['start_time'],endTime=b['end_time'])
        data.update(kwargs)
        return data
    def test_create_auth_privacy_persistence(self):
        r=self.store.create(self.general())
        self.assertEqual('approved',r['status'])
        self.assertEqual(r['id'],self.store.authenticate(dict(id=r['id'],password='booking-password')))
        self.assert_api(401,lambda:self.store.authenticate(dict(id=r['id'],password='wrong')))
        public=json.dumps(self.store.public(),ensure_ascii=False)
        self.assertNotIn('20260001',public)
        self.assertNotIn('booking-password',public)
        self.assertEqual(1,len(Store(self.path,self.store.clock).public()['events']))
    def test_duplicate_people(self):
        self.assert_api(400,lambda:self.store.create(self.general(attendees=[self.people[0],self.people[0]])))
    def test_overlap_adjacent_and_overnight(self):
        self.store.create(self.general(startTime='23:00',endTime='01:00'))
        self.assert_api(409,lambda:self.store.create(self.general(periodStart='2026-10-15',periodEnd='2026-10-15',startTime='00:30',endTime='01:30')))
        self.store.create(self.general(periodStart='2026-10-15',periodEnd='2026-10-15',startTime='01:00',endTime='02:00'))
    def test_limit_uses_student_id(self):
        self.store.create(self.general())
        data=self.general(startTime='17:00',endTime='19:00',name='다른이름',attendees=[dict(name='다른이름',studentId='20260001'),self.people[1]])
        self.assert_api(409,lambda:self.store.create(data))
    def test_calendar_day_limit(self):
        self.store.create(self.general(startTime='23:00',endTime='01:00'))
        self.store.create(self.general(periodStart='2026-10-15',periodEnd='2026-10-15',startTime='02:00',endTime='04:00'))
        self.assert_api(409,lambda:self.store.create(self.general(periodStart='2026-10-15',periodEnd='2026-10-15',startTime='05:00',endTime='05:10')))
    def test_pending_approval_rechecks_conflicts(self):
        r=self.store.create(self.regular())
        self.assertEqual([],self.store.public()['events'])
        self.store.create(self.general())
        self.assert_api(409,lambda:self.store.edit(r['id'],dict(action='approve',version=1),True))
        self.assertEqual('pending',self.store.get(r['id'])['status'])
    def test_approval_edit_requires_review(self):
        r=self.store.create(self.regular())
        b=self.store.edit(r['id'],dict(action='approve',version=1),True)
        self.assertEqual('approved',b['status'])
        self.assertTrue(self.store.public()['events'])
        b=self.store.edit(r['id'],self.edit_data(b,startTime='17:00',endTime='18:00'))
        self.assertEqual('pending',b['status'])
        self.assertEqual([],self.store.public()['events'])
    def test_future_month_edit_rejected(self):
        r=self.store.create(self.regular())
        b=self.store.get(r['id'])
        self.assert_api(400,lambda:self.store.edit(r['id'],self.edit_data(b,periodStart='2027-01-01',periodEnd='2027-01-31')))
    def test_edit_cancel_and_stale_version(self):
        r=self.store.create(self.general())
        b=self.store.get(r['id'])
        edited=self.store.edit(r['id'],self.edit_data(b,startTime='17:00',endTime='19:00'))
        self.assertEqual(2,edited['version'])
        self.assert_api(409,lambda:self.store.edit(r['id'],dict(action='cancel',version=1)))
        self.store.edit(r['id'],dict(action='cancel',version=2))
        self.assertEqual([],self.store.public()['events'])
    def test_row_identity_after_other_cancellation(self):
        a=self.store.create(self.general())
        b=self.store.create(self.general(periodStart='2026-10-15',periodEnd='2026-10-15'))
        self.store.edit(a['id'],dict(action='cancel',version=1))
        self.store.edit(b['id'],dict(action='cancel',version=1))
        self.assertEqual('cancelled',self.store.get(a['id'])['status'])
        self.assertEqual('cancelled',self.store.get(b['id'])['status'])
    def test_concurrent_booking_only_one_wins(self):
        barrier=threading.Barrier(4)
        def book(_):
            store=Store(self.path,self.store.clock)
            barrier.wait()
            try: store.create(self.general());return 'ok'
            except ApiError as e:return e.status
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(book,range(4)))
        self.assertEqual(1,results.count('ok'))
        self.assertEqual(3,results.count(409))
    def test_limits_and_reception_toggle(self):
        self.assert_api(400,lambda:self.store.create(self.general(endTime='14:00')))
        self.assert_api(400,lambda:self.store.create(self.general(periodStart='2026-11-20',periodEnd='2026-11-20')))
        with self.store.connect() as db: db.execute('UPDATE settings SET enabled=0')
        self.assert_api(403,lambda:self.store.create(self.general()))


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=make_server(0,Path(self.tmp.name)/'http.sqlite',admin_password='test-admin-password')
        self.server.state.store.clock=lambda:datetime(2026,10,13,9,tzinfo=KST)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,path,data=None,cookie='',origin=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        headers={'Cookie':cookie}
        body=None
        if data is not None:
            body=json.dumps(data)
            headers.update({'Content-Type':'application/json','Origin':origin or self.server.origin})
        conn.request('POST' if data is not None else 'GET',path,body,headers)
        response=conn.getresponse()
        raw=response.read()
        result=json.loads(raw) if response.getheader('Content-Type','').startswith('application/json') else raw
        status=response.status
        cookie=response.getheader('Set-Cookie','').split(';')[0]
        conn.close()
        return status,result,cookie
    def test_static_private_auth_csrf(self):
        self.assertEqual(200,self.request('/')[0])
        self.assertEqual(404,self.request('/server.py')[0])
        self.assertEqual(401,self.request('/api/admin')[0])
        self.assertEqual(403,self.request('/api/login',{},origin='https://evil.invalid')[0])
        status,_,cookie=self.request('/api/login',dict(role='admin',username='admin',password='test-admin-password'))
        self.assertEqual(200,status)
        self.assertEqual(200,self.request('/api/admin',cookie=cookie)[0])
    def test_booking_session_cannot_edit_other_reservation(self):
        people=[dict(name='대표',studentId='20260001'),dict(name='동반',studentId='20260002')]
        data=dict(kind='general',**people[0],attendees=people,periodStart='2026-10-14',periodEnd='2026-10-14',startTime='14:00',endTime='15:00',password='booking-password')
        a=self.server.state.store.create(data)
        data.update(periodStart='2026-10-15',periodEnd='2026-10-15')
        b=self.server.state.store.create(data)
        status,_,cookie=self.request('/api/login',dict(id=a['id'],password='booking-password'))
        self.assertEqual(200,status)
        status,result,_=self.request('/api/edit',dict(id=b['id'],action='cancel',version=1),cookie)
        self.assertEqual(200,status)
        self.assertEqual(a['id'],result['booking']['id'])
        self.assertEqual('approved',self.server.state.store.get(b['id'])['status'])


if __name__=='__main__': unittest.main()
