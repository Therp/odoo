# -*- coding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.     
#
##############################################################################

from caldav import common
from dateutil.rrule import *
from osv import fields, osv
import  datetime
import base64
import re
import time
import tools

class crm_meeting(osv.osv):
    _name = 'crm.meeting'    
    _description = "Meeting Cases"
    _order = "id desc"
    _inherits = {'crm.case':"inherit_case_id"}    
    __attribute__ = {
        'class' : {'field':'class', 'type':'text'}, 
        'created' : {'field':'create_date', 'type':'datetime'}, # keep none for now
        'description' : {'field':'description', 'type':'text'}, 
        'dtstart' : {'field':'date', 'type':'datetime'}, 
        #'last-mod' : {'field':'write_date', 'type':'datetime'},
        'location' : {'field':'location', 'type':'text'}, 
#        'organizer' : {'field':'partner_id', 'sub-field':'name', 'type':'many2one'}, 
        'priority' : {'field':'priority', 'type':'int'}, 
        'dtstamp'  : {'field':'date', 'type':'datetime'}, 
        'seq' : None, 
        'status' : {'field':'state', 'type':'selection', 'mapping' : {'TENTATIVE' : 'draft', \
                                                  'CONFIRMED' : 'open' , 'CANCELLED' : 'cancel'}}, 
        'summary' : {'field':'name', 'type':'text'}, 
        'transp' : {'field':'transparent', 'type':'text'}, 
        'uid' : {'field':'id', 'type':'text'}, 
        'url' : {'field':'caldav_url', 'type':'text'}, 
        'recurid' : None, 
#        'attach' : {'field':'attachment_ids', 'sub-field':'datas', 'type':'list'}, 
        'attendee' : {'field':'attendees', 'type':'many2many', 'object' : 'crm.caldav.attendee'}, 
#        'categories' : {'field':'categ_id', 'sub-field':'name'},
#        'categories' : {'field':None , 'sub-field':'name', 'type':'text'}, 
        'comment' : None, 
        'contact' : None, 
        'exdate'  : {'field':'exdate', 'type':'datetime'}, 
        'exrule'  : {'field':'exrule', 'type':'text'}, 
        'rstatus' : None, 
        'related' : None, 
        'resources' : None, 
        'rdate' : None, 
        'rrule' : {'field':'rrule', 'type':'text'}, 
        'x-openobject-model' : {'value':_name, 'type':'text'}, 
#        'duration' : {'field':'duration'},
        'dtend' : {'field':'date_closed', 'type':'datetime'}, 
        'valarm' : {'field':'alarm_id', 'type':'many2one', 'object' : 'crm.caldav.alarm'}, 
    }   

    _columns = {
        'inherit_case_id': fields.many2one('crm.case','Case',ondelete='cascade'),
        'class' : fields.selection([('PUBLIC', 'PUBLIC'), ('PRIVATE', 'PRIVATE'), \
                 ('CONFIDENTIAL', 'CONFIDENTIAL')], 'Privacy'), 
        'location' : fields.char('Location', size=264, help="Gives Location of Meeting"), 
        'freebusy' : fields.text('FreeBusy'), 
        'transparent' : fields.selection([('TRANSPARENT', 'TRANSPARENT'), \
                                          ('OPAQUE', 'OPAQUE')], 'Trensparent'), 
        'caldav_url' : fields.char('Caldav URL', size=264), 
        'exdate' : fields.text('Exception Date/Times', help="This property defines the list\
                 of date/time exceptions for arecurring calendar component."), 
        'exrule' : fields.char('Exception Rule', size=352, help="defines a rule or repeating pattern\
                                 for anexception to a recurrence set"), 
        'rrule' : fields.char('Recurrent Rule', size=352), 
        'attendees': fields.many2many('crm.caldav.attendee', 'crm_attendee_rel', 'case_id', \
                                      'attendee_id', 'Attendees'), 
        'alarm_id' : fields.many2one('crm.caldav.alarm', 'Alarm'), 
    }

    _defaults = {             
             'class': lambda *a: 'PUBLIC', 
             'transparent': lambda *a: 'OPAQUE', 
    }
    
    
    def run_scheduler(self, cr, uid, automatic=False, use_new_cursor=False, \
                       context=None):
        if not context:
            context = {}
        cr.execute('select c.id as id, crm_case.date as date, alarm.id as alarm_id, alarm.name as name,\
                                alarm.trigger_interval, alarm.trigger_duration, alarm.trigger_related, \
                                alarm.trigger_occurs from crm_meeting c \
                                    join crm_case on c.inherit_case_id = crm_case.id \
                                   join crm_caldav_alarm alarm on (alarm.id=c.alarm_id) \
                               where alarm_id is not null and alarm.active=True')
        case_with_alarm = cr.dictfetchall() 
        case_obj = self.pool.get('crm.meeting')
        attendee_obj = self.pool.get('crm.caldav.attendee')
        mail_to = []
        for alarmdata in case_with_alarm:
            dtstart = datetime.datetime.strptime(alarmdata['date'], "%Y-%m-%d %H:%M:%S")
            if alarmdata['trigger_interval'] == 'DAYS':
                delta = datetime.timedelta(days=alarmdata['trigger_duration'])
            if alarmdata['trigger_interval'] == 'HOURS':
                delta = datetime.timedelta(hours=alarmdata['trigger_duration'])
            if alarmdata['trigger_interval'] == 'MINUTES':
                delta = datetime.timedelta(minutes=alarmdata['trigger_duration'])
            alarm_time =  dtstart + (alarmdata['trigger_occurs']== 'AFTER' and delta or -delta)
            if datetime.datetime.now() >= alarm_time:
                case_val = case_obj.browse(cr, uid, alarmdata.get('id'), context)[0]
                for att in case_val.attendees:
                    if att.cn.rsplit(':')[-1]:
                        mail_to.append(att.cn.rsplit(':')[-1])
                if mail_to:
                    sub = 'Event Reminder for ' +  case_val.name or '' 
                    body = (case_val.name or '')+ '\n\t' + (case_val.description or '') + '\n\nEvent time: ' \
                                    +(case_val.date) + '\n\nLocation: ' + (case_val.location or '') + \
                                    '\n\nMembers Details: ' + '\n'.join(mail_to)
                    tools.email_send(
                        case_val.user_id.address_id.email, 
                        mail_to, 
                        sub, 
                        body
                    )
                cr.execute('update crm_caldav_alarm set active=False\
                         where id = %s' % alarmdata['alarm_id'])
                cr.commit()
        return True

    def export_cal(self, cr, uid, ids, context={}):
        crm_data = self.read(cr, uid, ids, [], context ={'read' :True})
        event_obj = self.pool.get('caldav.event')
        event_obj.__attribute__.update(self.__attribute__)
        
        attendee_obj = self.pool.get('caldav.attendee')
        crm_attendee = self.pool.get('crm.caldav.attendee')
        attendee_obj.__attribute__.update(crm_attendee.__attribute__)
        
        alarm_obj = self.pool.get('caldav.alarm')
        crm_alarm = self.pool.get('crm.caldav.alarm')
        alarm_obj.__attribute__.update(crm_alarm.__attribute__)
        
        ical = event_obj.export_ical(cr, uid, crm_data, {'model': 'crm.meeting'})
        caendar_val = ical.serialize()
        caendar_val = caendar_val.replace('"', '').strip()
        return caendar_val

    def import_cal(self, cr, uid, data, context={}):
        file_content = base64.decodestring(data)
        event_obj = self.pool.get('caldav.event')
        event_obj.__attribute__.update(self.__attribute__)

        attendee_obj = self.pool.get('caldav.attendee')
        crm_attendee = self.pool.get('crm.caldav.attendee')
        attendee_obj.__attribute__.update(crm_attendee.__attribute__)
        
        alarm_obj = self.pool.get('caldav.alarm')
        crm_alarm = self.pool.get('crm.caldav.alarm')
        alarm_obj.__attribute__.update(crm_alarm.__attribute__)
        vals = event_obj.import_ical(cr, uid, file_content)
        for val in vals:
            section_id = self.pool.get('crm.case.section').search(cr, uid, \
                            [('name', 'like', 'Meeting%')])[0]
            val.update({'section_id' : section_id})
            is_exists = common.uid2openobjectid(cr, val['id'], self._name )
            val.pop('id')
            if val.has_key('create_date'): val.pop('create_date')
            val['caldav_url'] = context.get('url') or ''
            if is_exists:
                self.write(cr, uid, [is_exists], val)
            else:
                case_id = self.create(cr, uid, val)
        return {'count': len(vals)}

    def search(self, cr, uid, args, offset=0, limit=None, order=None, 
            context=None, count=False):
        res = super(crm_meeting, self).search(cr, uid, args, offset, 
                limit, order, context, count)
        return res

    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        if isinstance(ids, (str, int, long)):
            select = [ids]
        else:
            select = ids
        new_ids = []
        for id in select:
            id = common.caldevIDs2readIDs(id)
            if not id in new_ids:
                new_ids.append(id)
        if 'case_id' in vals :
            vals['case_id'] = common.caldevIDs2readIDs(vals['case_id'])
        res = super(crm_meeting, self).write(cr, uid, new_ids, vals, context=context)
        return res

    def browse(self, cr, uid, ids, context=None, list_class=None, fields_process={}):
        if isinstance(ids, (str, int, long)):
            select = [ids]
        else:
            select = ids        
        select = map(lambda x:common.caldevIDs2readIDs(x), select)
        res = super(crm_meeting, self).browse(cr, uid, select, context, list_class, fields_process)        
        if isinstance(ids, (str, int, long)):
            return res and res[0] or False
        return res

    def read(self, cr, uid, ids, fields=None, context={},  load='_classic_read'):
        """         logic for recurrent event
         example : 123-20091111170822"""        
        if context and context.has_key('read'):
            return super(crm_meeting, self).read(cr, uid, ids, fields=fields, context=context, \
                                              load=load)
        if not type(ids) == list :
            # Called from code
            return super(crm_meeting, self).read(cr, uid, common.caldevIDs2readIDs(ids), \
                                                      fields=fields, context=context, load=load)
        else:
            ids = map(lambda x:common.caldevIDs2readIDs(x), ids)

        if fields and 'date' not in fields:
            fields.append('date')
        if not ids:
            return []
        result =  []
        for read_id in ids:
            res = super(crm_meeting, self).read(cr, uid, read_id, fields=fields, context=context, load=load)
            cr.execute("""select m.id, m.rrule, c.date, m.exdate from crm_meeting m\
                     join crm_case c on (c.id=m.inherit_case_id) \
                     where m.id = %s""" % read_id)
            data = cr.dictfetchall()[0]
            if not data['rrule']:
                strdate = ''.join((re.compile('\d')).findall(data['date']))
                idval = str(common.caldevIDs2readIDs(data['id'])) + '-' + strdate
                data['id'] = idval
                res.update(data)
                result.append(res)
            else:
                exdate = data['exdate'] and data['exdate'].split(',') or []
                event_obj = self.pool.get('caldav.event')
                rdates = event_obj.get_recurrent_dates(str(data['rrule']), exdate, data['date'])[:10]
                for rdate in rdates:
                    val = res.copy()
                    idval = (re.compile('\d')).findall(rdate)
                    val['date'] = rdate
                    id = str(res['id']).split('-')[0]
                    val['id'] = id + '-' + ''.join(idval)
                    val1 = val.copy()
                    result.append(val1)
        return result

    def copy(self, cr, uid, id, default=None, context={}):        
        return super(crm_meeting, self).copy(cr, uid, common.caldevIDs2readIDs(id), \
                                                          default, context)

    def unlink(self, cr, uid, ids, context=None):
        for id in ids:
            if len(str(id).split('-')) > 1:
                date_new = time.strftime("%Y-%m-%d %H:%M:%S", \
                                 time.strptime(str(str(id).split('-')[1]), "%Y%m%d%H%M%S"))
                for record in self.read(cr, uid, [common.caldevIDs2readIDs(id)], \
                                            ['date', 'rdates', 'rrule', 'exdate']):
                    if record['rrule']:
                        exdate = (record['exdate'] and (record['exdate'] + ',' )  or '') + \
                                    ''.join((re.compile('\d')).findall(date_new)) + 'Z'
                        if record['date'] == date_new:
                            self.write(cr, uid, [common.caldevIDs2readIDs(id)], {'exdate' : exdate})
                    else:
                        ids = map(lambda x:common.caldevIDs2readIDs(x), ids)
                        return super(crm_meeting, self).unlink(cr, uid, common.caldevIDs2readIDs(ids))
            else:
                return super(crm_meeting, self).unlink(cr, uid, ids)

    def create(self, cr, uid, vals, context={}):
        if 'case_id' in vals:
            vals['case_id'] = common.caldevIDs2readIDs(vals['case_id'])
        return super(crm_meeting, self).create(cr, uid, vals, context)


    def _map_ids(self, method, cr, uid, ids, *args, **argv):
        case_data = self.browse(cr, uid, ids)
        new_ids = []
        for case in case_data:
            if case.inherit_case_id:
                new_ids.append(case.inherit_case_id.id)
        return getattr(self.pool.get('crm.case'),method)(cr, uid, new_ids, *args, **argv)


    def onchange_case_id(self, cr, uid, ids, *args, **argv):
        return self._map_ids('onchange_case_id',cr,uid,ids,*args,**argv)
    def onchange_partner_id(self, cr, uid, ids, *args, **argv):
        return self._map_ids('onchange_partner_id',cr,uid,ids,*args,**argv)
    def onchange_partner_address_id(self, cr, uid, ids, *args, **argv):
        return self._map_ids('onchange_partner_address_id',cr,uid,ids,*args,**argv)
    def onchange_categ_id(self, cr, uid, ids, *args, **argv):
        return self._map_ids('onchange_categ_id',cr,uid,ids,*args,**argv)
    def case_close(self,cr, uid, ids, *args, **argv):
        return self._map_ids('case_close',cr,uid,ids,*args,**argv)    
    def case_open(self,cr, uid, ids, *args, **argv):
        return self._map_ids('case_open',cr,uid,ids,*args,**argv)
    def case_cancel(self,cr, uid, ids, *args, **argv):
        return self._map_ids('case_cancel',cr,uid,ids,*args,**argv)
    def case_reset(self,cr, uid, ids, *args, **argv):
        return self._map_ids('case_reset',cr,uid,ids,*args,**argv)
    

crm_meeting()


class crm_meeting_generic_wizard(osv.osv_memory):
    _name = 'crm.meeting.generic_wizard'

    _columns = {
        'section_id': fields.many2one('crm.case.section', 'Section', required=True),
        'user_id': fields.many2one('res.users', 'Responsible'),
    }

    def _get_default_section(self, cr, uid, context):
        case_id = context.get('active_id',False)
        if not case_id:
            return False
        case_obj = self.pool.get('crm.meeting')
        case = case_obj.read(cr, uid, case_id, ['state','section_id'])
        if case['state'] in ('done'):
            raise osv.except_osv(_('Error !'), _('You can not assign Closed Case.'))
        return case['section_id']


    _defaults = {
        'section_id': _get_default_section
    }
    def action_create(self, cr, uid, ids, context=None):
        case_obj = self.pool.get('crm.meeting')
        case_id = context.get('active_id',[])
        res = self.read(cr, uid, ids)[0]
        case = case_obj.read(cr, uid, case_id, ['state'])
        if case['state'] in ('done'):
            raise osv.except_osv(_('Error !'), _('You can not assign Closed Case.'))
        new_case_id = case_obj.copy(cr, uid, case_id, default=
                                            {
                                                'section_id':res.get('section_id',False),
                                                'user_id':res.get('user_id',False)
                                            }, context=context)        
        case_obj.write(cr, uid, case_id, {'case_id':new_case_id}, context=context)
        case_obj.case_close(cr, uid, [case_id])
        return {}

crm_meeting_generic_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
