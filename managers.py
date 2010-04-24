import datetime

from django.conf import settings
from django.db import connection, models

try:
    from django.db.models.sql.aggregates import Aggregate
except ImportError:
    supports_aggregates = False
else:
    supports_aggregates = True

from django.contrib.contenttypes.models import ContentType

if supports_aggregates:
    class CoalesceWrapper(Aggregate):
        sql_template = 'COALESCE(%(function)s(%(field)s), %(default)s)'
    
        def __init__(self, lookup, **extra): 
            self.lookup = lookup
            self.extra = extra
    
        def _default_alias(self):
            return '%s__%s' % (self.lookup, self.__class__.__name__.lower())
        default_alias = property(_default_alias)
    
        def add_to_query(self, query, alias, col, source, is_summary):
            super(CoalesceWrapper, self).__init__(col,
                                        source, is_summary, **self.extra)
            query.aggregate_select[alias] = self


    class CoalesceAvg(CoalesceWrapper):
        sql_function = 'AVG'


    class CoalesceCount(CoalesceWrapper):
        sql_function = 'COUNT'


class VoteManager(models.Manager):
    def get_score(self, obj):
        """
        Get a dictionary containing the total score for ``obj`` and
        the number of votes it's received.
        """
        ctype = ContentType.objects.get_for_model(obj)
        result = self.filter(object_id=obj._get_pk_val(),
                             content_type=ctype).extra(
            select={
                'score': 'COALESCE(AVG(vote), 0)',
                'num_votes': 'COALESCE(COUNT(vote), 0)',
        }).values_list('score', 'num_votes')[0]

        num_votes = int(result[1])
        if not num_votes:
            score = 0
        else:
            score = result[0]
                    
        return {
            'score': score,
            'num_votes': num_votes,
        }

    def get_scores_in_bulk(self, objects):
        """
        Get a dictionary mapping object ids to total score and number
        of votes for each object.
        """
        object_ids = [o._get_pk_val() for o in objects]
        if not object_ids:
            return {}
        
        ctype = ContentType.objects.get_for_model(objects[0])
        
        if supports_aggregates:
            queryset = self.filter(
                object_id__in = object_ids,
                content_type = ctype,
            ).values(
                'object_id',
            ).annotate(
                score = CoalesceAvg('vote', default='0'),
                num_votes = CoalesceCount('vote', default='0'),
            )
        else:
            queryset = self.filter(
                object_id__in = object_ids,
                content_type = ctype,
                ).extra(
                    select = {
                        'score': 'COALESCE(AVG(vote), 0)',
                        'num_votes': 'COALESCE(COUNT(vote), 0)',
                    }
                ).values('object_id', 'score', 'num_votes')
            queryset.query.group_by.append('object_id')
        
        vote_dict = {}
        for row in queryset:
            num_votes = row['num_votes']
            if not num_votes:
                score = 0
            else:
                score = row['score']
                
            vote_dict[row['object_id']] = {
                'score': score,
                'num_votes': num_votes,
            }
        
        return vote_dict

    def record_vote(self, obj, vote, ip, user):
        """
        Record a user's vote on a given object. Only allows a given user
        to vote once, though that vote may be changed.

        A zero vote indicates that any existing vote should be removed.
        """
        changed = False
        if not user.is_authenticated():
            user = None
        
        if vote not in (1, 2, 3, 4, 5):
            raise ValueError('Invalid vote')
        ctype = ContentType.objects.get_for_model(obj)
        try:
            v = self.get(user=user, ip=ip, content_type=ctype,
                         object_id=obj._get_pk_val())
            if vote == 0:
                v.delete()
            else:
                v.vote = vote
                v.save()
            changed = True
        except models.ObjectDoesNotExist:
            if vote != 0:
                self.create(user=user, ip=ip, content_type=ctype,
                            object_id=obj._get_pk_val(), vote=vote)
        return changed

    def get_top_of_month(self, Model, month=None, year=None, limit=10):
        today = datetime.datetime.now()
        one_month = datetime.timedelta(days=30)

        if not month:
            start_date = today - one_month
            end_date = today
        else:
            start_date = datetime.datetime(year or today.year, month, 1)
            end_date = start_date + one_month
        
        return self.get_top(Model, limit,
                            start_date=start_date, end_date=end_date)

    def get_top_of_week(self, Model, week=None, year=None, limit=10):
        now = datetime.datetime.now()
        
        week = week or now.isocalendar()[1]
        year = year or now.year
        
        d = datetime.date(year, 1, 1)
        
        if d.weekday() > 3:
            d = d + datetime.timedelta(7 - d.weekday())
        else:
            d = d - datetime.timedelta(d.weekday())
        delta = datetime.timedelta(days=(week-1)*7)
        
        start_date = d + dlt
        end_date = d + dlt + datetime.timedelta(days=6)
        
        return self.get_top(Model, limit,
                            start_date=start_date, end_date=end_date)

    def get_top(self, Model, limit=10, reversed=False,
                        start_date=None, end_date=None):
        """
        Get the top N scored objects for a given model.

        Yields (object, score) tuples.
        """
        if isinstance(Model, models.Manager):
            manager = Model
            Model = Model.model
        else:
            manager = Model.objects
        
        where = ''
        if start_date:
            where += 'AND date >= "%s"' % start_date 
        if end_date:
            where += 'AND date <= "%s"' % end_date
                
        ctype = ContentType.objects.get_for_model(Model)
        query = """
        SELECT object_id, AVG(vote) as %s
        FROM %s
        WHERE content_type_id = %%s %s
        GROUP BY object_id""" % (
            connection.ops.quote_name('score'),
            connection.ops.quote_name(self.model._meta.db_table), where,
        )

        # MySQL has issues with re-using the aggregate function in the
        # HAVING clause, so we alias the score and use this alias for
        # its benefit.
        if settings.DATABASE_ENGINE == 'mysql':
            having_score = connection.ops.quote_name('score')
        else:
            having_score = 'AVG(vote)'
        if reversed:
            having_sql = ' HAVING %(having_score)s < 0 \
                           ORDER BY %(having_score)s ASC LIMIT %%s'
        else:
            having_sql = ' HAVING %(having_score)s > 0 \
                           ORDER BY %(having_score)s DESC LIMIT %%s'
        query += having_sql % {
            'having_score': having_score,
        }

        cursor = connection.cursor()
        cursor.execute(query, [ctype.id, limit])
        results = cursor.fetchall()

        # Use in_bulk() to avoid O(limit) db hits.
        objects = manager.in_bulk([id for id, score in results])

        # Yield each object, score pair. Because of the lazy nature of generic
        # relations, missing objects are silently ignored.
        for id, score in results:
            if id in objects:
                yield objects[id], int(score)

    def get_bottom(self, Model, limit=10):
        """
        Get the bottom (i.e. most negative) N scored objects for a given
        model.

        Yields (object, score) tuples.
        """
        return self.get_top(Model, limit, True)

    def get_for_user(self, obj, user):
        """
        Get the vote made on the given object by the given user, or
        ``None`` if no matching vote exists.
        """
        if not user.is_authenticated():
            return None
        ctype = ContentType.objects.get_for_model(obj)
        try:
            vote = self.get(content_type=ctype, object_id=obj._get_pk_val(),
                            user=user)
        except models.ObjectDoesNotExist:
            vote = None
        return vote

    def get_for_user_in_bulk(self, objects, user):
        """
        Get a dictionary mapping object ids to votes made by the given
        user on the corresponding objects.
        """
        vote_dict = {}
        if len(objects) > 0:
            ctype = ContentType.objects.get_for_model(objects[0])
            votes = list(self.filter(content_type__pk=ctype.id,
                                     object_id__in=[obj._get_pk_val() \
                                                    for obj in objects],
                                     user__pk=user.id))
            vote_dict = dict([(vote.object_id, vote) for vote in votes])
        return vote_dict