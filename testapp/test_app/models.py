from django.db import models
from datetime import datetime

class Person(models.Model):
    id = models.AutoField(primary_key=True)
    has_dependents = models.BooleanField(core=True)
    first_name = models.CharField(maxlength=200)
    dress_size = models.CommaSeparatedIntegerField(maxlength=20)
    
    creation_date = models.DateTimeField(auto_now_add=True)
    last_update = models.DateTimeField(auto_now=True)
    
    birthday = models.DateField(auto_now_add=True)
    
    height = models.DecimalField(max_digits=5, decimal_places=2)
    personal_email = models.EmailField()
    fan_mail = models.FileField(upload_to='upload')
    fan_mail_store = models.FilePathField(path='/home/barbie/fan_mail/')
    weight = models.FloatField()
    # Image Field
    net_worth = models.IntegerField()
    static_ip = models.IPAddressField()
    has_partner = models.NullBooleanField()
    phone_number = models.PhoneNumberField()
    unofficial_age = models.PositiveIntegerField()
    pin_number = models.PositiveSmallIntegerField()
    personal_motto = models.SlugField(maxlength=200)
    small_integer = models.SmallIntegerField()
    life_story = models.TextField()
    last_coffee = models.TimeField(auto_now=True)
    personal_website = models.URLField(verify_exists=False, maxlength=200)
    us_state = models.USStateField()
    # XMLField
    
    personal_transport = models.ForeignKey('Vehicle')
    friends = models.ManyToManyField('self', symmetrical=True)
    local_representative = models.ManyToManyField('GovernmentRepresentative')
    
    class Meta:
        unique_together = (("id", "first_name", "birthday"),)
        verbose_name = 'Person'
        verbose_name_plural = 'People'
  
class Vehicle(models.Model):
    license_plate = models.CharField(maxlength=9)
    description = models.TextField()
    
class GovernmentRepresentative(models.Model):
    base_person = models.OneToOneField(Person)
    
    class Meta:
        db_table = 'gov_representative'


