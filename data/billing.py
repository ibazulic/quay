import random
import string
import sys
from calendar import timegm
from datetime import datetime, timedelta
from typing import Any, Dict

import stripe

from util.morecollections import AttrDict

PLANS = [
    # Deprecated Plans (2013-2014)
    {
        "title": "Micro",
        "price": 700,
        "privateRepos": 5,
        "stripeId": "micro",
        "audience": "For smaller teams",
        "bus_features": False,
        "deprecated": True,
        "free_trial_days": 14,
        "superseded_by": "personal-30",
        "plans_page_hidden": False,
    },
    {
        "title": "Basic",
        "price": 1200,
        "privateRepos": 10,
        "stripeId": "small",
        "audience": "For your basic team",
        "bus_features": False,
        "deprecated": True,
        "free_trial_days": 14,
        "superseded_by": "bus-micro-30",
        "plans_page_hidden": False,
    },
    {
        "title": "Yacht",
        "price": 5000,
        "privateRepos": 20,
        "stripeId": "bus-coreos-trial",
        "audience": "For small businesses",
        "bus_features": True,
        "deprecated": True,
        "free_trial_days": 180,
        "superseded_by": "bus-small-30",
        "plans_page_hidden": False,
    },
    {
        "title": "Personal",
        "price": 1200,
        "privateRepos": 5,
        "stripeId": "personal",
        "audience": "Individuals",
        "bus_features": False,
        "deprecated": True,
        "free_trial_days": 14,
        "superseded_by": "personal-30",
        "plans_page_hidden": False,
    },
    {
        "title": "Skiff",
        "price": 2500,
        "privateRepos": 10,
        "stripeId": "bus-micro",
        "audience": "For startups",
        "bus_features": True,
        "deprecated": True,
        "free_trial_days": 14,
        "superseded_by": "bus-micro-30",
        "plans_page_hidden": False,
    },
    {
        "title": "Yacht",
        "price": 5000,
        "privateRepos": 20,
        "rh_sku": "FakeSKU",
        "stripeId": "bus-small",
        "audience": "For small businesses",
        "bus_features": True,
        "deprecated": True,
        "free_trial_days": 14,
        "superseded_by": "bus-small-30",
        "plans_page_hidden": False,
    },
    {
        "title": "Freighter",
        "price": 10000,
        "privateRepos": 50,
        "stripeId": "bus-medium",
        "audience": "For normal businesses",
        "bus_features": True,
        "deprecated": True,
        "free_trial_days": 14,
        "superseded_by": "bus-medium-30",
        "plans_page_hidden": False,
    },
    {
        "title": "Tanker",
        "price": 20000,
        "privateRepos": 125,
        "stripeId": "bus-large",
        "audience": "For large businesses",
        "bus_features": True,
        "deprecated": True,
        "free_trial_days": 14,
        "superseded_by": "bus-large-30",
        "plans_page_hidden": False,
    },
    # Deprecated plans (2014-2017)
    {
        "title": "Personal",
        "price": 1200,
        "privateRepos": 5,
        "stripeId": "personal-30",
        "audience": "Individuals",
        "bus_features": False,
        "deprecated": True,
        "free_trial_days": 30,
        "superseded_by": "personal-2018",
        "plans_page_hidden": False,
    },
    {
        "title": "Skiff",
        "price": 2500,
        "privateRepos": 10,
        "stripeId": "bus-micro-30",
        "audience": "For startups",
        "bus_features": True,
        "deprecated": True,
        "free_trial_days": 30,
        "superseded_by": "bus-micro-2018",
        "plans_page_hidden": False,
    },
    {
        "title": "Yacht",
        "price": 5000,
        "privateRepos": 20,
        "stripeId": "bus-small-30",
        "audience": "For small businesses",
        "bus_features": True,
        "deprecated": True,
        "free_trial_days": 30,
        "superseded_by": "bus-small-2018",
        "plans_page_hidden": False,
    },
    {
        "title": "Freighter",
        "price": 10000,
        "privateRepos": 50,
        "stripeId": "bus-medium-30",
        "audience": "For normal businesses",
        "bus_features": True,
        "deprecated": True,
        "free_trial_days": 30,
        "superseded_by": "bus-medium-2018",
        "plans_page_hidden": False,
    },
    {
        "title": "Tanker",
        "price": 20000,
        "privateRepos": 125,
        "stripeId": "bus-large-30",
        "audience": "For large businesses",
        "bus_features": True,
        "deprecated": True,
        "free_trial_days": 30,
        "superseded_by": "bus-large-2018",
        "plans_page_hidden": False,
    },
    {
        "title": "Carrier",
        "price": 35000,
        "privateRepos": 250,
        "stripeId": "bus-xlarge-30",
        "audience": "For extra large businesses",
        "bus_features": True,
        "deprecated": True,
        "free_trial_days": 30,
        "superseded_by": "bus-xlarge-2018",
        "plans_page_hidden": False,
    },
    {
        "title": "Huge",
        "price": 65000,
        "privateRepos": 500,
        "stripeId": "bus-500-30",
        "audience": "For huge business",
        "bus_features": True,
        "deprecated": True,
        "free_trial_days": 30,
        "superseded_by": "bus-500-2018",
        "plans_page_hidden": False,
    },
    {
        "title": "Huuge",
        "price": 120000,
        "privateRepos": 1000,
        "stripeId": "bus-1000-30",
        "audience": "For the SaaS savvy enterprise",
        "bus_features": True,
        "deprecated": True,
        "free_trial_days": 30,
        "superseded_by": "bus-1000-2018",
        "plans_page_hidden": False,
    },
    # Active plans (as of Dec 2017)
    {
        "title": "Open Source",
        "price": 0,
        "privateRepos": 0,
        "stripeId": "free",
        "audience": "Committment to FOSS",
        "bus_features": False,
        "deprecated": False,
        "free_trial_days": 30,
        "superseded_by": None,
        "plans_page_hidden": False,
    },
    {
        "title": "Developer",
        "price": 1500,
        "privateRepos": 5,
        "stripeId": "personal-2018",
        "rh_sku": "MW00584MO",
        "sku_billing": False,
        "audience": "Individuals",
        "bus_features": False,
        "deprecated": False,
        "free_trial_days": 30,
        "superseded_by": None,
        "plans_page_hidden": False,
    },
    {
        "title": "Micro",
        "price": 3000,
        "privateRepos": 10,
        "rh_sku": "MW00585MO",
        "sku_billing": False,
        "stripeId": "bus-micro-2018",
        "audience": "For startups",
        "bus_features": True,
        "deprecated": False,
        "free_trial_days": 30,
        "superseded_by": None,
        "plans_page_hidden": False,
    },
    {
        "title": "Small",
        "price": 6000,
        "privateRepos": 20,
        "rh_sku": "MW00586MO",
        "sku_billing": False,
        "stripeId": "bus-small-2018",
        "audience": "For small businesses",
        "bus_features": True,
        "deprecated": False,
        "free_trial_days": 30,
        "superseded_by": None,
        "plans_page_hidden": False,
    },
    {
        "title": "Medium",
        "price": 12500,
        "privateRepos": 50,
        "rh_sku": "MW00587MO",
        "sku_billing": False,
        "stripeId": "bus-medium-2018",
        "audience": "For normal businesses",
        "bus_features": True,
        "deprecated": False,
        "free_trial_days": 30,
        "superseded_by": None,
        "plans_page_hidden": False,
    },
    {
        "title": "Large",
        "price": 25000,
        "privateRepos": 125,
        "rh_sku": "MW00588MO",
        "sku_billing": False,
        "stripeId": "bus-large-2018",
        "audience": "For large businesses",
        "bus_features": True,
        "deprecated": False,
        "free_trial_days": 30,
        "superseded_by": None,
        "plans_page_hidden": False,
    },
    {
        "title": "Extra Large",
        "price": 45000,
        "privateRepos": 250,
        "rh_sku": "MW00589MO",
        "billing_enabled": False,
        "stripeId": "bus-xlarge-2018",
        "audience": "For extra large businesses",
        "bus_features": True,
        "deprecated": False,
        "free_trial_days": 30,
        "superseded_by": None,
        "plans_page_hidden": False,
    },
    {
        "title": "XXL",
        "price": 85000,
        "privateRepos": 500,
        "rh_sku": "MW00590MO",
        "billing_enabled": False,
        "stripeId": "bus-500-2018",
        "audience": "For huge business",
        "bus_features": True,
        "deprecated": False,
        "free_trial_days": 30,
        "superseded_by": None,
        "plans_page_hidden": False,
    },
    {
        "title": "XXXL",
        "price": 160000,
        "privateRepos": 1000,
        "rh_sku": "MW00591MO",
        "sku_billing": False,
        "stripeId": "bus-1000-2018",
        "audience": "For the SaaS savvy enterprise",
        "bus_features": True,
        "deprecated": False,
        "free_trial_days": 30,
        "superseded_by": None,
        "plans_page_hidden": False,
    },
    {
        "title": "XXXXL",
        "price": 310000,
        "privateRepos": 2000,
        "rh_sku": "MW00592MO",
        "sku_billing": False,
        "stripeId": "bus-2000-2018",
        "audience": "For the SaaS savvy big enterprise",
        "bus_features": True,
        "deprecated": False,
        "free_trial_days": 30,
        "superseded_by": None,
        "plans_page_hidden": False,
    },
    {
        "title": "XXXXXL",
        "price": 2170000,
        "privateRepos": 15000,
        "stripeId": "price_1LRztA2OoNF1TIf0SvSrz106",
        "audience": "For the SaaS savvy very big enterprise",
        "bus_features": True,
        "deprecated": False,
        "free_trial_days": 30,
        "superseded_by": None,
        "plans_page_hidden": False,
    },
    {
        "title": "premium",
        "privateRepos": 100,
        "stripeId": "not_a_stripe_plan",
        "rh_sku": "MW02701",
        "sku_billing": True,
        "plans_page_hidden": True,
    },
    {
        "title": "selfsupport",
        "privateRepos": sys.maxsize,
        "stripeId": "not_a_stripe_plan",
        "rh_sku": "MW02702",
        "sku_billing": True,
        "plans_page_hidden": True,
    },
    {
        "title": "freetier",
        "privateRepos": 0,
        "stripeId": "not_a_stripe_plan",
        "rh_sku": "MW04192",
        "sku_billing": False,
        "plans_page_hidden": True,
    },
]

RH_SKUS = [plan["rh_sku"] for plan in PLANS if plan.get("rh_sku") is not None]

RECONCILER_SKUS = [
    plan["rh_sku"]
    for plan in PLANS
    if plan.get("rh_sku") is not None and not plan.get("sku_billing")
]


def get_plan(plan_id):
    """
    Returns the plan with the given ID or None if none.
    """
    for plan in PLANS:
        if plan["stripeId"] == plan_id:
            return plan

    return None


def get_plan_using_rh_sku(sku):
    """
    Returns the plan with given sku or None if none.
    """
    if sku is None:
        return None
    for plan in PLANS:
        if plan.get("rh_sku") == sku:
            return plan
    return None


class FakeStripe(object):
    ACTIVE_CUSTOMERS: Dict[str, Any] = {}

    class error(object):
        class InvalidRequestException(Exception):
            pass

        class APIConnectionError(Exception):
            pass

    class FakeSubscription(AttrDict):
        @classmethod
        def build(cls, data, customer):
            data = AttrDict.deep_copy(data)
            data["customer"] = customer
            data["id"] = "sub_" + "".join(random.choices(string.ascii_lowercase, k=14))
            return cls(data)

        @classmethod
        def delete(cls, sub_id):
            for _, cus_obj in FakeStripe.ACTIVE_CUSTOMERS.items():
                if cus_obj._subscription and cus_obj._subscription.id == sub_id:
                    cus_obj._subscription = None

        def default_payment_method(self, payment_method):
            return "pm_somestripepaymentmethodid"

    class Customer(AttrDict):
        FAKE_PLAN = AttrDict(
            {
                "id": "bus-small",
            }
        )

        FAKE_SUBSCRIPTION = AttrDict(
            {
                "plan": FAKE_PLAN,
                "current_period_start": timegm(datetime.utcnow().utctimetuple()),
                "current_period_end": timegm(
                    (datetime.utcnow() + timedelta(days=30)).utctimetuple()
                ),
                "trial_start": timegm(datetime.utcnow().utctimetuple()),
                "trial_end": timegm((datetime.utcnow() + timedelta(days=30)).utctimetuple()),
            }
        )

        FAKE_CARD = AttrDict(
            {
                "id": "card123",
                "name": "Joe User",
                "type": "Visa",
                "last4": "4242",
                "exp_month": 5,
                "exp_year": 2016,
            }
        )

        FAKE_CARD_LIST = AttrDict(
            {
                "data": [FAKE_CARD],
            }
        )

        @property
        def id(self):
            return self.get("id", None)

        @property
        def subscription(self):
            return FakeStripe.ACTIVE_CUSTOMERS[self.id]._subscription

        @property
        def card(self):
            return self.get("new_card", None)

        @card.setter
        def card(self, card_token):
            self["new_card"] = card_token

        @property
        def plan(self):
            return self.get("new_plan", None)

        @plan.setter
        def plan(self, plan_name):
            self["new_plan"] = plan_name

        def refresh(self):
            return self

        def save(self):
            if self.get("new_card", None) is not None:
                raise stripe.error.CardError(
                    "Test raising exception on set card.", self.get("new_card"), 402
                )
            if self.get("new_plan", None) is not None:
                if self._subscription is None:
                    self._subscription = FakeStripe.FakeSubscription.build(
                        self.FAKE_SUBSCRIPTION, self
                    )
                self._subscription.plan.id = self.get("new_plan")

        @classmethod
        def retrieve(cls, stripe_customer_id):
            if stripe_customer_id in FakeStripe.ACTIVE_CUSTOMERS:
                FakeStripe.ACTIVE_CUSTOMERS[stripe_customer_id].pop("new_card", None)
                FakeStripe.ACTIVE_CUSTOMERS[stripe_customer_id].pop("new_plan", None)

                return FakeStripe.ACTIVE_CUSTOMERS[stripe_customer_id]
            else:
                new_customer = cls(
                    {
                        "default_card": "card123",
                        "cards": AttrDict.deep_copy(cls.FAKE_CARD_LIST),
                        "id": stripe_customer_id,
                    }
                )

                FakeStripe.ACTIVE_CUSTOMERS[stripe_customer_id] = new_customer

                new_customer._subscription = FakeStripe.FakeSubscription.build(
                    cls.FAKE_SUBSCRIPTION, new_customer
                )

                return new_customer

        @classmethod
        def create(cls, **kwargs):
            cus_id = "cus_" + "".join(random.choices(string.ascii_lowercase, k=14))
            new_customer = cls(
                {
                    "default_card": "card123",
                    "cards": AttrDict.deep_copy(cls.FAKE_CARD_LIST),
                    "id": cus_id,
                }
            )
            new_customer._subscription = FakeStripe.FakeSubscription.build(
                cls.FAKE_SUBSCRIPTION, new_customer
            )
            FakeStripe.ACTIVE_CUSTOMERS[stripe_customer_id] = new_customer
            return new_customer

        @classmethod
        def modify(cls, cus_id, **kwargs):
            customer = FakeStripe.ACTIVE_CUSTOMERS.get(cus_id)
            if not customer:
                # For testing, assume customer exists
                customer = cls(
                    {
                        "default_card": "card123",
                        "cards": AttrDict.deep_copy(cls.FAKE_CARD_LIST),
                        "id": cus_id,
                    }
                )
                customer._subscription = FakeStripe.FakeSubscription.build(
                    cls.FAKE_SUBSCRIPTION, new_customer
                )
                FakeStripe.ACTIVE_CUSTOMERS[cus_id] = customer

            if kwargs.get("plan"):
                if customer._subscription is None:
                    customer._subscription = FakeStripe.FakeSubscription.build(
                        cls.FAKE_SUBSCRIPTION, customer
                    )
                customer._subscription.plan.id = kwargs.get("plan")

            return customer

    class Invoice(AttrDict):
        @staticmethod
        def list(customer, count):
            return AttrDict(
                {
                    "data": [],
                }
            )

    class PaymentMethod(AttrDict):
        FAKE_PAYMENT_METHOD = AttrDict(
            {
                "id": "card123",
                "type": "Visa",
                "card": AttrDict(
                    {
                        "last4": "4242",
                        "exp_month": 5,
                        "exp_year": 2016,
                    }
                ),
                "billing_details": AttrDict({"name": "Joe User"}),
            }
        )

        @classmethod
        def retrieve(cls, payment_method_id):
            return cls.FAKE_PAYMENT_METHOD

    Subscription = FakeSubscription


class Billing(object):
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.state = self.init_app(app)
        else:
            self.state = None

    def init_app(self, app):
        billing_type = app.config.get("BILLING_TYPE", "FakeStripe")

        if billing_type == "Stripe":
            billing = stripe
            stripe.api_key = app.config.get("STRIPE_SECRET_KEY", None)

        elif billing_type == "FakeStripe":
            billing = FakeStripe

        else:
            raise RuntimeError("Unknown billing type: %s" % billing_type)

        # register extension with app
        app.extensions = getattr(app, "extensions", {})
        app.extensions["billing"] = billing
        return billing

    def __getattr__(self, name):
        return getattr(self.state, name, None)
