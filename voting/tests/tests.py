test = r"""
>>> from django.contrib.auth.models import User
>>> from django.contrib.contenttypes.models import ContentType
>>> from voting.models import Vote
>>> from voting.tests.models import Item

##########
# Django PVoting #
##########

# Basic voting ###############################################################

>>> i1 = Item.objects.create(name='test1')
>>> ip = '192.168.1.1'
>>> users = []
>>> for username in (1, 2, 3, 4):
...     u = (User.objects.create_user(username, 'u%s@test.com' % username, 'test'), '192.168.1.%s' % username)
...     users.append(u)
>>> Vote.objects.get_score(i1)['score'] 
0
>>> Vote.objects.get_score(i1)['num_votes']
0
>>> Vote.objects.record_vote(i1, 1, users[0][1], users[0][0])
False
>>> Vote.objects.get_score(i1)['score']
1.0
>>> Vote.objects.get_score(i1)['num_votes']
1
>>> Vote.objects.record_vote(i1, 2, users[0][1], users[0][0])
True
>>> Vote.objects.get_score(i1)['score']                 
2.0                   
>>> Vote.objects.record_vote(i1, 0, users[0][1], users[0][0])
True
>>> Vote.objects.get_score(i1)['score']
0
>>> for user in users:
...     Vote.objects.record_vote(i1, 1, user[1], user[0])
False
False
False
False
>>> Vote.objects.get_score(i1)['score']              
1.0
>>> for user in users[:2]:                       
...     Vote.objects.record_vote(i1, 0, user[1], user[0])
True
True
>>> Vote.objects.get_score(i1)['score']               
1.0                    
>>> for user in users[:2]:                       
...     Vote.objects.record_vote(i1, 4, user[1], user[0])
False
False
>>> Vote.objects.get_score(i1)['score']
2.5
>>> Vote.objects.record_vote(i1, -2, user[1], user[0])
Traceback (most recent call last):
    ...
ValueError: Invalid vote

>>> Vote.objects.get_top_of_week(Item).next()
(<Item: test1>, 2)

# Retrieval of votes #########################################################

>>> i2 = Item.objects.create(name='test2')
>>> i3 = Item.objects.create(name='test3')
>>> i4 = Item.objects.create(name='test4')
>>> Vote.objects.record_vote(i2, 1, users[0][1], users[0][0])
False
>>> Vote.objects.record_vote(i3, 2, users[0][1], users[0][0])
False
>>> Vote.objects.record_vote(i4, 0, users[0][1], users[0][0])
False
>>> vote = Vote.objects.get_for_user(i2, users[0][0])
>>> vote.vote
1
>>> vote = Vote.objects.get_for_user(i3, users[0][0])
>>> vote.vote
2
>>> Vote.objects.get_for_user(i4, users[0][0]) is None
True

# In bulk
>>> votes = Vote.objects.get_for_user_in_bulk([i1, i2, i3, i4], users[0][0])
>>> [(id, vote.vote) for id, vote in votes.items()]
[(1, 4), (2, 1), (3, 2)]
>>> Vote.objects.get_for_user_in_bulk([], users[0][0])
{}
>>> for user in users[1:]:
...     Vote.objects.record_vote(i2, 4, user[1], user[0])
...     Vote.objects.record_vote(i3, 5, user[1], user[0])
...     Vote.objects.record_vote(i4, 4, user[1], user[0])
False
False
False
False
False
False
False
False
False
>>> list(Vote.objects.get_top(Item))
[(<Item: test3>, 4), (<Item: test4>, 4), (<Item: test2>, 3), (<Item: test1>, 2)]
>>> for user in users[1:]:
...     Vote.objects.record_vote(i2, 1, user[1], user[0])
...     Vote.objects.record_vote(i3, 2, user[1], user[0])
...     Vote.objects.record_vote(i4, 1, user[1], user[0])
True
True
True
True
True
True
True
True
True
>>> list(Vote.objects.get_bottom(Item))
[(<Item: test2>, 1), (<Item: test4>, 1), (<Item: test3>, 2)]
"""